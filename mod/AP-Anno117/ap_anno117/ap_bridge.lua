-- AP-Anno117 bridge: connects Anno 117 to the Archipelago client.
--
-- Game -> client: lines printed to the game log (and ap_outbox.txt when Lua has file access), e.g.
--     AP117|<seed>|CHECK|118149608
-- Client -> game: the client rewrites ap_state.lua next to this file. The bridge reads it at startup
-- (require), re-reads it while playing if the game allows that (io or dofile), and as a last resort
-- the client types data in through the keybinds defined in assets.xml.
--
-- Written for Luau (Anno 117) and kept Lua 5.1-compatible so it can be tested outside the game.

local AP = {}

AP.VERSION = "0.1.4"
AP.PROTOCOL = 1

-- ID scheme, shared with the apworld (gamedata.py)
local ITEM_BASE = 117000000
local FILLER_BASE = 117900000
local POP_BASE = 118000000
local BUILD_BASE = 119000000
local BUILD_END = 120000000
local DENARII = 1010017
local THRESHOLDS = { 10, 25, 50, 75, 100, 150, 200, 250, 300, 400, 500, 600, 750, 1000, 1250,
                     1500, 2000, 2500, 3000, 4000, 5000, 7500, 10000 }

local CYCLE_TICKS = 10        -- ~1 second at 10 ticks per second
local WARMUP_TICKS = 30       -- wait after loading a save before touching game state
local BUILD_CHECKS_PER_CYCLE = 8
local RELOCK_COOLDOWN = 5     -- cycles between relock attempts for the same building
local HEARTBEAT_CYCLES = 30
local SYNC_CYCLES = 120
local SYNC_CHUNK = 40
local GOAL_CYCLES = 5
local GOAL_REPEAT_CYCLES = 60

---------------------------------------------------------------------------------------------------
-- small helpers
---------------------------------------------------------------------------------------------------

local function int(n)
    return string.format("%d", math.floor(tonumber(n) or 0))
end

local function count_of(list)
    if list == nil then return 0 end
    local ok, n = pcall(function() return #list end)
    if ok and type(n) == "number" and n > 0 then return n end
    local c = 0
    pcall(function() for _ in pairs(list) do c = c + 1 end end)
    return c
end

local function script_dir()
    local src
    if debug and debug.info then
        local ok, s = pcall(debug.info, 1, "s")
        if ok then src = s end
    end
    if (not src) and debug and debug.getinfo then
        local ok, info = pcall(debug.getinfo, 1, "S")
        if ok and info then src = info.source end
    end
    if type(src) ~= "string" then return nil end
    src = src:gsub("^[@=]", ""):gsub("\\", "/")
    return src:match("^(.*/)[^/]*$")
end

local SCRIPT_DIR = script_dir()

---------------------------------------------------------------------------------------------------
-- state
---------------------------------------------------------------------------------------------------

local G = {
    startup = nil,         -- state table loaded with require at mod init
    current = nil,         -- last applied state table
    session = nil,         -- "seed|slot" of the applied state
    seed = "-",
    nonce = nil,
    loaded = false,
    ticks = 0,
    cycles = 0,
    received = {},         -- unlock GUID -> true
    locked = {},           -- GUID list to keep locked until received
    applied_index = 0,     -- highest consumable item index applied
    reported = {},         -- location id -> true
    reported_list = {},
    pending_pop = {},      -- active population locations
    pending_build = {},    -- active construction locations
    build_cursor = 1,
    relock_wait = {},
    goal_sent = false,
    source = "none",       -- where the current state came from
    live_reader = nil,     -- function returning a fresh state table, once one is known to work
    caps = {},
    errors = {},
    keys = { bits = {}, },
    forced = {},
    hello_sent = false,
    outbox = nil,
}
AP._G = G  -- exposed for tests

local function caps_string()
    local parts = {}
    for _, k in ipairs({ "io", "dofile", "debugsrc" }) do
        parts[#parts + 1] = k .. "=" .. (G.caps[k] and "1" or "0")
    end
    return table.concat(parts, ";")
end

local function out(kind, payload)
    local line = "AP117|" .. tostring(G.seed) .. "|" .. kind .. "|" .. (payload or "")
    print(line)
    if G.outbox and io and io.open then
        local ok, f = pcall(io.open, G.outbox, "a")
        if ok and f then
            pcall(function() f:write(line, "\n"); f:close() end)
        end
    end
end
AP.out = out

local function report_error(where, err)
    local msg = tostring(where) .. ": " .. tostring(err)
    local last = G.errors[msg]
    if last and G.cycles - last < 60 then return end
    G.errors[msg] = G.cycles
    out("ERR", msg:gsub("[\r\n|]", " "))
end

local function try(where, fn, ...)
    local ok, a, b = pcall(fn, ...)
    if not ok then
        report_error(where, a)
        return nil
    end
    return a, b
end

---------------------------------------------------------------------------------------------------
-- reading the state file
---------------------------------------------------------------------------------------------------

-- Parses the line format the client writes ("S.key = value"), for when we can only read text.
function AP.parse_state_text(text)
    if type(text) ~= "string" or text == "" then return nil end
    local S = {}
    local found = false
    for line in text:gmatch("[^\r\n]+") do
        local key, value = line:match("^%s*S%.([%w_]+)%s*=%s*(.-)%s*$")
        if key then
            found = true
            local first = value:sub(1, 1)
            if first == "{" then
                local list = {}
                for n in value:gmatch("%-?%d+") do list[#list + 1] = tonumber(n) end
                S[key] = list
            elseif first == '"' then
                S[key] = value:match('^"(.*)"$') or ""
            else
                S[key] = tonumber(value)
            end
        end
    end
    if not found then return nil end
    return S
end

local function state_dirs()
    local dirs = {}
    local seen = {}
    local function add(d)
        if type(d) == "string" and d ~= "" and not seen[d] then
            seen[d] = true
            dirs[#dirs + 1] = d
        end
    end
    if G.current then add(G.current.mod_dir) end
    if G.startup then add(G.startup.mod_dir) end
    add(SCRIPT_DIR)
    return dirs
end

local DOFILE_RELATIVE = {
    "ap_anno117/ap_state.lua",
    "mods/AP-Anno117/ap_anno117/ap_state.lua",
    "data/ap_anno117/ap_state.lua",
}

local function read_with_io(path)
    local ok, f = pcall(io.open, path, "r")
    if not ok or not f then return nil end
    local text
    pcall(function() text = f:read("*a") end)
    pcall(function() f:close() end)
    return AP.parse_state_text(text)
end

-- The state file both returns its table and sets the global AP117_STATE; use whichever this game's
-- dofile/require gives us (sandboxed chunks may not share our globals).
local function read_with_dofile(path)
    local previous = AP117_STATE
    AP117_STATE = nil
    local ok, ret = pcall(dofile, path)
    local S = (ok and type(ret) == "table" and ret) or AP117_STATE
    if not ok or type(S) ~= "table" then
        AP117_STATE = previous
        return nil
    end
    return S
end

-- Finds a way to read the state file while the game runs. Returns a state table or nil.
local function read_live_state()
    if G.live_reader then
        local S = G.live_reader()
        if S then return S end
    end
    if G.caps.io then
        for _, dir in ipairs(state_dirs()) do
            local path = dir .. "ap_state.lua"
            local S = read_with_io(path)
            if S then
                G.live_reader = function() return read_with_io(path) end
                G.source = "io"
                G.outbox = dir .. "ap_outbox.txt"
                return S
            end
        end
    end
    if G.caps.dofile then
        local paths = {}
        for _, dir in ipairs(state_dirs()) do paths[#paths + 1] = dir .. "ap_state.lua" end
        for _, p in ipairs(DOFILE_RELATIVE) do paths[#paths + 1] = p end
        for _, path in ipairs(paths) do
            local S = read_with_dofile(path)
            if S then
                G.live_reader = function() return read_with_dofile(path) end
                G.source = "dofile"
                return S
            end
        end
    end
    return nil
end

local function load_startup_state()
    for _, name in ipairs({ "ap_state", "ap_anno117/ap_state", "ap_anno117.ap_state" }) do
        local ok, res = pcall(require, name)
        local S = (ok and type(res) == "table" and res) or AP117_STATE
        if type(S) == "table" then
            G.startup = S
            return
        end
    end
end

---------------------------------------------------------------------------------------------------
-- game actions
---------------------------------------------------------------------------------------------------

local function is_unlocked(guid)
    local ok, res = pcall(function() return Unlock:IsUnlocked(guid) end)
    return ok and res == true
end

local function unlock(guid)
    try("unlock " .. int(guid), function() Unlock:UnlockNet(guid) end)
end

local function relock(guid)
    try("relock " .. int(guid), function() Unlock:RelockNet(guid) end)
end

local function add_denarii(amount)
    return try("denarii", function()
        Economy.MetaStorage:AddAmount(DENARII, amount)
        return true
    end)
end

local function population(level, current)
    if current then
        local ok, n = pcall(function() return Population:GetGlobalPopulationCount(level) end)
        if ok and type(n) == "number" then return n end
    end
    local ok, n = pcall(function() return Population:GetMaxReachedGlobalPopulationCount(level) end)
    if ok and type(n) == "number" then return n end
    if not current then
        ok, n = pcall(function() return Population:GetGlobalPopulationCount(level) end)
        if ok and type(n) == "number" then return n end
    end
    return 0
end

local function owned_count(guid)
    local owner
    pcall(function() owner = Participants.GetCurrentParticipantGUID end)
    if owner ~= nil then
        local ok, list = pcall(function() return Scripts:GetObjectGroupByGUID(guid, owner) end)
        if ok and list ~= nil then return count_of(list) end
    end
    local ok, list = pcall(function() return Scripts:GetObjectGroupByGUID(guid) end)
    if not ok or list == nil then return 0 end
    local c = 0
    pcall(function()
        for _, obj in pairs(list) do
            local mine = true
            pcall(function() mine = obj.IsOwnedByCurrentParticipant ~= false end)
            if mine then c = c + 1 end
        end
    end)
    return c
end

---------------------------------------------------------------------------------------------------
-- applying state and items
---------------------------------------------------------------------------------------------------

local function reset_session()
    G.received = {}
    G.forced = {}
    G.reported = {}
    G.reported_list = {}
    G.relock_wait = {}
    G.goal_sent = false
    G.applied_index = 0
end

local function apply_item(index, id, S)
    id = tonumber(id)
    index = tonumber(index) or 0
    if not id then return end
    if id >= ITEM_BASE and id < FILLER_BASE then
        local guid = id - ITEM_BASE
        if not G.received[guid] then
            G.received[guid] = true
            unlock(guid)
        end
    elseif id >= FILLER_BASE and id < POP_BASE then
        if index > G.applied_index then
            local amount = tonumber(S and S.denarii) or tonumber(G.current and G.current.denarii) or 10000
            if add_denarii(amount) then
                G.applied_index = index
                out("APPLIED", int(index))
            end
        end
    end
end
AP.apply_item = apply_item

-- Unlocks something the seed does not shuffle (a residence the game itself is holding back). Anything the
-- seed locks stays locked until it is received, so this can never hand out an item early.
local function force_unlock(guid)
    guid = tonumber(guid)
    if not guid then return false end
    for _, locked in ipairs(G.locked or {}) do
        if tonumber(locked) == guid and not G.received[guid] then
            out("ERR", "refused unlock " .. int(guid) .. ": shuffled in this seed")
            return false
        end
    end
    if not G.forced[guid] then
        G.forced[guid] = true
        unlock(guid)
        out("UNLOCKED", int(guid))
    end
    return true
end
AP.force_unlock = force_unlock

local function set_locations(S)
    G.pending_pop = {}
    G.pending_build = {}
    for _, id in ipairs(S.locations or {}) do
        id = tonumber(id)
        if id and not G.reported[id] then
            if id >= POP_BASE and id < BUILD_BASE then
                G.pending_pop[#G.pending_pop + 1] = id
            elseif id >= BUILD_BASE and id < BUILD_END then
                G.pending_build[#G.pending_build + 1] = id
            end
        end
    end
    G.build_cursor = 1
end

local function apply_state(S, source)
    if type(S) ~= "table" or tonumber(S.protocol or 0) ~= AP.PROTOCOL or not S.seed or S.seed == "" then
        return false
    end
    local session = tostring(S.seed) .. "|" .. tostring(S.slot or "")
    if session ~= G.session then
        reset_session()
        G.session = session
        G.seed = tostring(S.seed)
    end
    G.current = S
    G.source = source or G.source
    if tonumber(S.consumed) and tonumber(S.consumed) > G.applied_index then
        G.applied_index = tonumber(S.consumed)
    end
    G.locked = S.locked or {}
    set_locations(S)
    for index, id in ipairs(S.items or {}) do
        apply_item(index, id, S)
    end
    for _, guid in ipairs(S.unlock or {}) do
        force_unlock(guid)
    end
    if S.nonce ~= nil and S.nonce ~= G.nonce then
        G.nonce = S.nonce
        out("ACK", int(S.nonce))
    end
    return true
end
AP.apply_state = apply_state

---------------------------------------------------------------------------------------------------
-- checks, locks and goal
---------------------------------------------------------------------------------------------------

local function report(id)
    if G.reported[id] then return end
    G.reported[id] = true
    G.reported_list[#G.reported_list + 1] = id
    out("CHECK", int(id))
end

local function check_population()
    local keep = {}
    local cache = {}
    for _, id in ipairs(G.pending_pop) do
        local rel = id - POP_BASE
        local level = math.floor(rel / 100)
        local threshold = THRESHOLDS[(rel % 100) + 1]
        if cache[level] == nil then cache[level] = population(level, false) end
        if threshold and cache[level] >= threshold then
            report(id)
        else
            keep[#keep + 1] = id
        end
    end
    G.pending_pop = keep
end

local function check_buildings()
    local n = #G.pending_build
    if n == 0 then return end
    local done = {}
    for _ = 1, math.min(BUILD_CHECKS_PER_CYCLE, n) do
        if G.build_cursor > n then G.build_cursor = 1 end
        local id = G.pending_build[G.build_cursor]
        if owned_count(id - BUILD_BASE) > 0 then
            report(id)
            done[id] = true
        end
        G.build_cursor = G.build_cursor + 1
    end
    if next(done) then
        local keep = {}
        for _, id in ipairs(G.pending_build) do
            if not done[id] then keep[#keep + 1] = id end
        end
        G.pending_build = keep
    end
end

local function enforce_locks()
    for _, guid in ipairs(G.locked) do
        if not G.received[guid] then
            local wait = G.relock_wait[guid]
            if (not wait or G.cycles >= wait) and is_unlocked(guid) then
                relock(guid)
                G.relock_wait[guid] = G.cycles + RELOCK_COOLDOWN
            end
        end
    end
end

-- Residences the seed does not shuffle: the game normally unlocks them through progress the randomizer can hold
-- back (production buildings you don't have yet). S.auto_unlock lists {tier, residence} pairs: once the tier below
-- has residents, its upgrade is unlocked. Upgrading still needs the residents' needs met, as usual.
local function auto_unlock_residences()
    local list = G.current and G.current.auto_unlock
    if type(list) ~= "table" then return end
    for i = 1, #list - 1, 2 do
        local tier, residence = tonumber(list[i]), tonumber(list[i + 1])
        if tier and residence and not G.forced[residence] and population(tier, false) > 0 then
            force_unlock(residence)
        end
    end
end
AP.auto_unlock_residences = auto_unlock_residences

local function check_goal()
    local S = G.current
    if not S or not S.goal or #S.goal == 0 then return end
    -- once reached, repeat about once a minute in case the client was not watching
    if G.goal_sent and G.cycles % GOAL_REPEAT_CYCLES ~= 0 then return end
    local need = tonumber(S.goal_count) or 0
    for _, level in ipairs(S.goal) do
        if population(level, true) < need then return end
    end
    out("GOAL", int(need))
    G.goal_sent = true
end

---------------------------------------------------------------------------------------------------
-- keybind channel (fallback): the client presses KeyBit(0/1) for each bit, then KeyEnd
---------------------------------------------------------------------------------------------------

local function checksum(s)
    local sum = 0
    for i = 1, #s do sum = (sum + s:byte(i)) % 251 end
    return sum
end
AP.checksum = checksum

local function handle_key_message(msg)
    local body, sum = msg:match("^(.*)%*(%d+)$")
    if not body or tonumber(sum) ~= checksum(body) then
        out("KEYERR", "checksum," .. (#msg * 8))
        return
    end
    local kind, rest = body:sub(1, 1), body:sub(2)
    if kind == "P" then
        out("KEYACK", rest)
    elseif kind == "I" then
        local index, offset = rest:match("^(%d+),(%d+)$")
        if index then
            apply_item(tonumber(index), ITEM_BASE + tonumber(offset), G.current)
            out("KEYGOT", index)
        else
            out("KEYERR", "item")
        end
    elseif kind == "U" then
        force_unlock(rest)
        out("KEYGOT", "U" .. rest)
    elseif kind == "C" then
        local n = tonumber(rest)
        if n and n > G.applied_index then G.applied_index = n end
        out("KEYGOT", "C" .. rest)
    else
        out("KEYERR", "kind")
    end
end
AP.handle_key_message = handle_key_message

function AP.KeyBit(bit)
    local bits = G.keys.bits
    bits[#bits + 1] = (bit == 1) and 1 or 0
end

function AP.KeyReset()
    G.keys.bits = {}
end

function AP.KeyEnd()
    local bits = G.keys.bits
    G.keys.bits = {}
    if #bits == 0 or #bits % 8 ~= 0 then
        out("KEYERR", "length," .. #bits)
        return
    end
    local chars = {}
    for i = 1, #bits, 8 do
        local byte = 0
        for j = 0, 7 do byte = byte * 2 + bits[i + j] end
        chars[#chars + 1] = string.char(byte)
    end
    try("keys", handle_key_message, table.concat(chars))
end

function AP.RequestItems()
    out("REQ", int(G.applied_index))
end

---------------------------------------------------------------------------------------------------
-- hooks (modinfo.json)
---------------------------------------------------------------------------------------------------

local function hello()
    out("HELLO", int(AP.PROTOCOL) .. "," .. AP.VERSION .. "," .. caps_string() .. "," .. G.source
        .. "," .. (G.nonce ~= nil and int(G.nonce) or "-"))
    G.hello_sent = true
end

local function cycle()
    G.cycles = G.cycles + 1
    local fresh = read_live_state()
    if fresh and fresh.nonce ~= G.nonce then
        apply_state(fresh, G.source)
    elseif not G.current and G.startup then
        apply_state(G.startup, "startup")
    end
    if not G.hello_sent then hello() end
    if not G.current then return end

    check_population()
    check_buildings()
    if G.cycles % 2 == 0 then enforce_locks() end
    if G.cycles % 5 == 0 then auto_unlock_residences() end
    if G.cycles % GOAL_CYCLES == 0 then check_goal() end
    if G.cycles % HEARTBEAT_CYCLES == 0 then
        out("HB", int(G.applied_index) .. "," .. int(#G.pending_pop + #G.pending_build))
    end
    if G.cycles % SYNC_CYCLES == 0 then AP.Sync() end
end

-- Re-announces every check found this session, in short lines (the client may have started late).
function AP.Sync()
    local ids = {}
    for _, id in ipairs(G.reported_list) do
        ids[#ids + 1] = int(id)
        if #ids >= SYNC_CHUNK then
            out("SYNC", table.concat(ids, ","))
            ids = {}
        end
    end
    if #ids > 0 then out("SYNC", table.concat(ids, ",")) end
end

-- For the in-game script console: prints what the bridge currently knows.
function AP.Status()
    out("STATUS", "source=" .. G.source .. ";caps=" .. caps_string() .. ";items=" ..
        int(G.current and count_of(G.current.items) or 0) .. ";applied=" .. int(G.applied_index) ..
        ";reported=" .. int(#G.reported_list) .. ";pending=" .. int(#G.pending_pop + #G.pending_build) ..
        ";locked=" .. int(#G.locked))
end

function AP.OnLoad()
    G.loaded = true
    G.ticks = 0
    G.current = nil
    G.session = nil
    G.nonce = nil
    G.hello_sent = false
    reset_session()
end

function AP.OnUnload()
    G.loaded = false
end

function AP.OnTick()
    if not G.loaded then return end
    G.ticks = G.ticks + 1
    if G.ticks < WARMUP_TICKS or G.ticks % CYCLE_TICKS ~= 0 then return end
    try("cycle", cycle)
end

-- init
G.caps.io = (type(io) == "table" and type(io.open) == "function") or false
G.caps.dofile = type(dofile) == "function"
G.caps.debugsrc = SCRIPT_DIR ~= nil
pcall(load_startup_state)
if G.startup and G.startup.seed then G.seed = tostring(G.startup.seed) end

return AP

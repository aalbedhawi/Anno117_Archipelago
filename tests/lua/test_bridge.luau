-- Runs the AP-Anno117 bridge against a mocked Anno 117 API in the Luau CLI.
--   luau tests/lua/test_bridge.luau
local failures = 0
local passes = 0
local function check(cond, label)
    if cond then
        passes += 1
    else
        failures += 1
        print("FAIL: " .. label)
    end
end

---------------------------------------------------------------------------- mocks
local lines = {}
local realprint = print
print = function(...)
    local parts = {}
    for i = 1, select("#", ...) do parts[#parts + 1] = tostring(select(i, ...)) end
    lines[#lines + 1] = table.concat(parts, " ")
end

local unlocked = { [2693] = true }   -- Wheat Farm starts unlocked by "vanilla" progression
local calls = { unlock = {}, relock = {}, denarii = 0, denarii_calls = 0 }
Unlock = {
    IsUnlocked = function(self, guid) return unlocked[guid] == true end,
    UnlockNet = function(self, guid) unlocked[guid] = true; calls.unlock[#calls.unlock + 1] = guid end,
    RelockNet = function(self, guid) unlocked[guid] = nil; calls.relock[#calls.relock + 1] = guid end,
}
local pop_max = { [1499] = 15 }
local pop_now = { [1498] = 0 }
Population = {
    GetMaxReachedGlobalPopulationCount = function(self, level) return pop_max[level] or 0 end,
    GetGlobalPopulationCount = function(self, level) return pop_now[level] or 0 end,
}
local objects = { [3174] = { "obj" } }
Participants = { GetCurrentParticipantGUID = 41 }
Scripts = {
    GetObjectGroupByGUID = function(self, guid, owner)
        assert(owner == 41, "owner passed")
        return objects[guid] or {}
    end,
}
Economy = { MetaStorage = { AddAmount = function(self, guid, amount)
    assert(guid == 1010017)
    calls.denarii += amount
    calls.denarii_calls += 1
end } }

local files = {}
dofile = function(path)
    local fn = files[path]
    if not fn then error("no file " .. path) end
    fn()
end

local startup = {
    protocol = 1, nonce = 1, seed = "SEED1", slot = "Marcus", denarii = 5000, consumed = 0,
    goal_count = 100, goal = { 1498 },
    locked = { 3141, 2693, 3174 },
    locations = { 118149900, 118149903, 119003174 },
    items = { 117003141, 117900001, 117003174 },
    mod_dir = "C:/mods/AP-Anno117/ap_anno117/",
}
require = function(name)
    if name == "ap_state" then
        AP117_STATE = startup
        return startup
    end
    error("unexpected require " .. tostring(name))
end

-- run_bridge_tests.py inlines ap_bridge.lua here, so it shares globals with these mocks like it does in game
local AP = (function()
--@@BRIDGE@@
end)()
check(type(AP) == "table", "bridge loads")
check(AP._G.startup == startup, "startup state from require")

local function tick(n)
    for _ = 1, n do AP.OnTick() end
end
local function find(prefix)
    for _, l in ipairs(lines) do
        if l:sub(1, #prefix) == prefix then return l end
    end
    return nil
end
local function count_prefix(prefix)
    local c = 0
    for _, l in ipairs(lines) do
        if l:sub(1, #prefix) == prefix then c += 1 end
    end
    return c
end

---------------------------------------------------------------------------- 1: startup session
AP.OnLoad()
tick(29)
check(#lines == 0, "nothing during warmup")
tick(1)
check(find("AP117|SEED1|HELLO|1," .. AP.VERSION .. ",") ~= nil, "hello sent: " .. tostring(lines[#lines]))
check(find("AP117|SEED1|ACK|1") ~= nil, "ack for startup nonce")
check(table.find(calls.unlock, 3141) ~= nil, "residence unlocked")
check(table.find(calls.unlock, 3174) ~= nil, "bakery unlocked")
check(calls.denarii == 5000 and calls.denarii_calls == 1, "one denarii cache applied")
check(find("AP117|SEED1|APPLIED|2") ~= nil, "applied index reported")
check(find("AP117|SEED1|CHECK|118149900") ~= nil, "10 Liberti milestone")
check(find("AP117|SEED1|CHECK|118149903") == nil, "75 Liberti not yet")
check(find("AP117|SEED1|CHECK|119003174") ~= nil, "bakery built check")
tick(10)
check(table.find(calls.relock, 2693) ~= nil, "wheat farm relocked")
check(table.find(calls.relock, 3141) == nil, "received residence not relocked")

---------------------------------------------------------------------------- 2: population grows
pop_max[1499] = 80
tick(10)
check(find("AP117|SEED1|CHECK|118149903") ~= nil, "75 Liberti after growth")
check(count_prefix("AP117|SEED1|CHECK|118149900") == 1, "milestone reported once")
AP.Sync()
check(find("AP117|SEED1|SYNC|118149900,119003174,118149903") ~= nil, "sync lists every check")

---------------------------------------------------------------------------- 3: live update via dofile
files["C:/mods/AP-Anno117/ap_anno117/ap_state.lua"] = function()
    AP117_STATE = {
        protocol = 1, nonce = 2, seed = "SEED1", slot = "Marcus", denarii = 5000, consumed = 0,
        goal_count = 100, goal = { 1498 },
        locked = { 3141, 2693, 3174 },
        locations = { 119003174 },
        items = { 117003141, 117900001, 117003174, 117002693, 117900001 },
        mod_dir = "C:/mods/AP-Anno117/ap_anno117/",
    }
end
tick(10)
check(find("AP117|SEED1|ACK|2") ~= nil, "ack for live nonce")
check(AP._G.source == "dofile", "live source is dofile")
check(table.find(calls.unlock, 2693) ~= nil, "wheat farm unlocked by item")
check(calls.denarii == 10000 and calls.denarii_calls == 2, "second cache only")
local relocks_before = #calls.relock
tick(40)
local relocked_again = false
for i = relocks_before + 1, #calls.relock do
    if calls.relock[i] == 2693 then relocked_again = true end
end
check(not relocked_again, "received building stays unlocked")

---------------------------------------------------------------------------- 4: reload keeps consumed caches
files["C:/mods/AP-Anno117/ap_anno117/ap_state.lua"] = function()
    AP117_STATE = {
        protocol = 1, nonce = 3, seed = "SEED1", slot = "Marcus", denarii = 5000, consumed = 5,
        goal_count = 100, goal = { 1498 },
        locked = { 3141, 2693, 3174 }, locations = {},
        items = { 117003141, 117900001, 117003174, 117002693, 117900001 },
        mod_dir = "C:/mods/AP-Anno117/ap_anno117/",
    }
end
AP.OnUnload()
AP.OnLoad()
tick(30)
check(calls.denarii_calls == 2, "no caches re-applied after reload")
check(count_prefix("AP117|SEED1|HELLO") == 2, "hello again after load")

---------------------------------------------------------------------------- 5: goal
pop_now[1498] = 150
tick(50)
check(find("AP117|SEED1|GOAL|100") ~= nil, "goal reached")
local goals = count_prefix("AP117|SEED1|GOAL")
tick(50)
check(count_prefix("AP117|SEED1|GOAL") == goals, "goal not spammed every cycle")

---------------------------------------------------------------------------- 6: key channel
local function send_keys(msg)
    local framed = msg .. "*" .. tostring(AP.checksum(msg))
    for i = 1, #framed do
        local b = framed:byte(i)
        for j = 7, 0, -1 do
            AP.KeyBit(bit32.extract(b, j))
        end
    end
    AP.KeyEnd()
end
send_keys("P4242")
check(find("AP117|SEED1|KEYACK|4242") ~= nil, "key ping acked")
send_keys("I6,900001")
check(find("AP117|SEED1|KEYGOT|6") ~= nil, "key item acked")
check(find("AP117|SEED1|APPLIED|6") ~= nil and calls.denarii_calls == 3, "key item applied")
send_keys("I6,900001")
check(calls.denarii_calls == 3, "duplicate key item ignored")
AP.KeyBit(1); AP.KeyBit(0); AP.KeyEnd()
check(find("AP117|SEED1|KEYERR|length") ~= nil, "bad length rejected")
local framed = "P1*99"
for i = 1, #framed do
    local b = framed:byte(i)
    for j = 7, 0, -1 do AP.KeyBit(bit32.extract(b, j)) end
end
AP.KeyEnd()
check(find("AP117|SEED1|KEYERR|checksum") ~= nil, "bad checksum rejected")

---------------------------------------------------------------------------- 6b: residence unlocks (/unlock_residence)
send_keys("U3142")
check(unlocked[3142] == true, "typed unlock of an unshuffled residence")
check(find("AP117|SEED1|UNLOCKED|3142") ~= nil and find("AP117|SEED1|KEYGOT|U3142") ~= nil, "unlock confirmed")
local saved_locked = AP._G.locked
AP._G.locked = { 9999 }
check(AP.force_unlock(9999) == false and unlocked[9999] == nil, "shuffled, unreceived guid refused")
check(find("AP117|SEED1|ERR|refused unlock 9999") ~= nil, "refusal reported")
AP._G.locked = saved_locked
local before = #calls.unlock
AP.force_unlock(3142)
check(#calls.unlock == before, "unlock not repeated")

---------------------------------------------------------------------------- 6c: automatic residence unlocks
AP._G.current.auto_unlock = { 1496, 3142, 1497, 3145 }   -- Plebeians -> Eques Residence, Equites -> Patrician Residence
AP._G.forced[3142] = nil
unlocked[3142] = nil
pop_max[1496] = 0
AP.auto_unlock_residences()
check(unlocked[3142] == nil, "no unlock before the tier below has residents")
pop_max[1496] = 12
AP.auto_unlock_residences()
check(unlocked[3142] == true, "Eques Residence unlocked once Plebeians live there")
check(unlocked[3145] == nil, "Patrician Residence waits for Equites")
AP._G.locked = { 3145 }
pop_max[1497] = 5
AP.auto_unlock_residences()
check(unlocked[3145] == nil, "a shuffled residence is never auto-unlocked")
AP._G.locked = saved_locked
AP._G.current.auto_unlock = nil

---------------------------------------------------------------------------- 7: text parser (io mode)
local parsed = AP.parse_state_text(table.concat({
    "-- comment",
    "AP117_STATE = {}",
    "local S = AP117_STATE",
    "S.protocol = 1",
    "S.nonce = 77",
    'S.seed = "1234"',
    "S.items = {117003141,117900001}",
    "S.locations = {}",
    'S.mod_dir = "C:/Users/x/Documents/Anno 117/mods/AP-Anno117/ap_anno117/"',
    "return AP117_STATE",
}, "\n"))
check(parsed and parsed.nonce == 77 and parsed.seed == "1234", "parse scalars")
check(parsed and #parsed.items == 2 and parsed.items[2] == 117900001, "parse list")
check(parsed and #parsed.locations == 0, "parse empty list")
check(parsed and parsed.mod_dir == "C:/Users/x/Documents/Anno 117/mods/AP-Anno117/ap_anno117/", "parse path")

---------------------------------------------------------------------------- 8: status and sync
AP.Status()
check(find("AP117|SEED1|STATUS|source=dofile") ~= nil, "status line")

realprint(string.format("luau bridge tests: %d passed, %d failed", passes, failures))
if failures > 0 then
    for _, l in ipairs(lines) do realprint("  " .. l) end
    error("bridge tests failed")
end

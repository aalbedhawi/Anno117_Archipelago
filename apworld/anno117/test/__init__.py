from test.bases import WorldTestBase

from ..world import Anno117World


class Anno117TestBase(WorldTestBase):
    game = "Anno 117"
    world: Anno117World

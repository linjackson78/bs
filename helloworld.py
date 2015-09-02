import bs

# scripts specify an API-version they were written against
# so the game knows to ignore out-of-date ones.
def bsGetAPIVersion():
    return 3
# how BombSquad asks us what games we provide
def bsGetGames():
    return [HelloWorldGame]

class HelloWorldGame(bs.TeamGameActivity):

    @classmethod
    def getName(cls):
        return 'Hello World Game'

    @classmethod
    def getDescription(cls,sessionType):
        return 'Just a test game.'

    def onBegin(self):
        bs.TeamGameActivity.onBegin(self)
        # game's starting - let's just set a timer to end it in 5 seconds
        bs.screenMessage("Hello World!  Ending in 5 seconds...")
        self._endGameTimer = bs.Timer(5000,bs.WeakCall(self.endGame))

    def endGame(self):
        # game's over - set a score for each team and tell our activity to finish
        ourResults = bs.TeamGameResults()
        for team in self.teams: ourResults.setTeamScore(team,0)
        self.end(results=ourResults)
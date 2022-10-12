from random2Agent import RandomAgent

PRODUCE = 0
BUYPRODUCE = 1
BUYWARES = 2
AUCTION = 3
PASS = 4
SAILSEA = 5
BUYFACT = 6
BUYWAREHOUSE = 7

class BestRandomAgent(RandomAgent):
    def __init__(self,game,id):
        super().__init__(game,id)
        self.name = "BestRandom2Agent"
        self.verbose = False

    #FUNCTIONS FROM BEST_AGENT
    #JUST TO PREVENT OVERBIDDING
    def accept_bid(self,bid,product,buyer,bids):
        bid_value = bid*2 if not self.game.monopoly_mode else bid

        if (bid_value > min(self.containers_score(self.playerID,product)-bid,self.game.player_cash[self.playerID])):
            return True
        else:
            return False

    # HOW MUCH IS CONTIANERS ACTUALLY WORTH TO PLAYER
    # product = [x for each colour]
    def containers_score(self, player, product):
        value = 0
        for i in range(self.game.NUM_CONTAINERS):
            value += product[i]*self.game.player_cards[player][i]
        return value

    def get_bid(self, product):
        self_value = min(self.containers_score(self.playerID,product),self.game.player_cash[self.playerID])

        best_bidder = 0
        for i in range(self.game.NUM_PLAYERS):
            if i != self.playerID and i != self.game.active_player:
                bidder_value = min(self.containers_score(i,product),self.game.player_cash[i])

                if bidder_value > best_bidder:
                    best_bidder = bidder_value

        owner_value = self.containers_score(self.game.active_player,product)
        if (self.verbose): print(f"Bid Analysis, self {self_value}, seller {owner_value}, bidder {best_bidder}")
        return min(self_value, max(best_bidder, round(owner_value/2)))


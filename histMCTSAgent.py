import copy
import math
from mctsAgent import MCTSNode,MCTSAgent,ISMCTSNode
from history2Agent import HistoryAgent

PRODUCE = 0
BUYPRODUCE = 1
BUYWARES = 2
AUCTION = 3
PASS = 4
SAILSEA = 5
BUYFACT = 6
BUYWAREHOUSE = 7

PERFECT = 0 # can see score cards
SEMI_PERFECT = 1 # info set limited
HIDDEN = 2

class HistMCTSAgent(MCTSAgent):
    def __init__(self,game,id):
        super().__init__(game,id)
        self.name = "HistMCTSAgent"
        self.verbose = False

        # from hist agent
        self.ignore_selfbids = True
        self.MIN_CAPITAL = 4

    # sim using best random instead of random
    def createRoot(self, base_game):
        modified_game = copy.deepcopy(base_game)
        modified_game.verbose = False
        modified_game.anticheat = False
        modified_game.logfile = ""
        for x in range(modified_game.NUM_PLAYERS):
            modified_game.players[x] = HistoryAgent(modified_game,x)

        if self.game.INFO_MODE == PERFECT: return MCTSNode(modified_game,-1,-1)
        elif self.game.INFO_MODE == SEMI_PERFECT: return ISMCTSNode(modified_game,-1,-1,self.infosets,ROLLOUT_SHORTCUT=False)

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

    #FUNCTIONS FROM HIST_AGENT
    def est_price(self,colour,type=BUYPRODUCE):
        sum = 0
        count = 0
        log = self.game.ware_log
        if type == BUYPRODUCE: log = self.game.prod_log
        for x in log: #(turn0, price1, colour2, seller3, buyer4)
            if x[2] == colour:
                if ((self.ignore_selfbids and [4] != self.playerID) or not self.ignore_selfbids):
                    count += 1
                    sum += x[1]

        if (count == 0): 
            if type == BUYPRODUCE: return 1 # min sale price at Fact
            else: return 2 # min sale price at WH
        return math.floor(sum/count)

    # out = [(value,colour),...] asc order
    def est_prices(self,type=BUYPRODUCE,sorted = True):
        out = []
        for x in range(self.game.NUM_CONTAINERS):
            out.append((self.est_price(x,type),x))
        if (sorted): out.sort(key=lambda x: x[0])

        return out

    def factory_reprice(self):
        self.produce_est = self.est_prices(type = BUYPRODUCE) # value of product
        self.produce_est_sorted = copy.deepcopy(self.produce_est)
        self.produce_est_sorted.sort(key=lambda x: x[0])
        
        goods = self.game.player_produce[self.playerID]

        #drop overflow
        total = self.game.get_numProduce()
        cap = self.game.get_numFacts()
        count = total - cap*2
        if (count > 0):
            if (self.game.verbose): print("Before Drop ", goods)
            for x in range(self.game.NUM_CONTAINERS):
                colour = self.produce_est_sorted[x][1]
                if (count > 0):
                    if (count > len(goods[colour])):
                        count -= len(goods[colour])
                        self.game.player_produce[self.playerID][colour] = []
                    else:
                        self.game.player_produce[self.playerID][colour] = self.game.player_produce[self.playerID][colour][count:]
                        break
                else:
                    break
            if (self.game.verbose): print("After Drop ",self.game.player_produce[self.playerID])

        #reprice
        for type in range(len(goods)):
            for item in range(len(goods[type])-1,-1,-1):
                goods[type][item] = self.produce_est[type][0] # sets price to 1
            goods[type].sort()

    def warehouse_reprice(self,player,cart):
        self.wares_est = self.est_prices(type = BUYWARES) # value of wares
        self.wares_est_sorted = copy.deepcopy(self.wares_est)
        self.wares_est_sorted.sort(key=lambda x: x[0])

        goods = self.game.player_wares[self.playerID]

        #drop overflow
        total = self.game.get_numWares()
        cap = self.game.get_numWarehouses()
        count = total - cap*2
        if (count > 0):
            if (self.game.verbose): print("Before Drop ", goods)
            for x in range(self.game.NUM_CONTAINERS):
                colour = self.wares_est_sorted[x][1]
                if (count > 0):
                    if (count > len(goods[colour])):
                        count -= len(goods[colour])
                        self.game.player_wares[self.playerID][colour] = []
                    else:
                        self.game.player_wares[self.playerID][colour] = self.game.player_wares[self.playerID][colour][count:]
                        break
                else:
                    break
            if (self.game.verbose): print("After Drop ",self.game.player_wares[self.playerID])

        #reprice
        for type in range(len(goods)):
            for item in range(len(goods[type])-1,-1,-1):
                goods[type][item] = self.wares_est[type][0] # sets price to 2
            goods[type].sort()
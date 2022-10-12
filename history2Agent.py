#from math import prod
import random
import math
import copy
from bestAgent import BestAgent

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

class HistoryAgent(BestAgent):
    def __init__(self,game,id):
        super().__init__(game,id)
        self.name = "HistoryAgent"
        self.verbose = False
        self.ignore_selfbids = True
        self.MIN_CAPITAL = 4

        self.scorecard_est = self.est_score_cards() if not self.game.INFO_MODE == PERFECT else False
        self.produce_est = self.est_prices(type = BUYPRODUCE) # value of product
        self.produce_est_sorted = copy.deepcopy(self.produce_est)
        self.produce_est_sorted.sort(key=lambda x: x[0])
        self.wares_est = self.est_prices(type = BUYWARES) # value of wares
        self.wares_est_sorted = copy.deepcopy(self.wares_est)
        self.wares_est_sorted.sort(key=lambda x: x[0])

    # Best Agent move policy is should give expected value
    # bid policy perfect info calculate (no discount)
    # repricing policy is product:1, warehouse:2
    def make_move(self):
        # historical bids, TODO only winning bids, to ignore false bids, probably weight wins?
        self.scorecard_est = self.est_score_cards() if not self.game.INFO_MODE == PERFECT else False
        self.produce_est = self.est_prices(type = BUYPRODUCE) # value of product
        self.produce_est_sorted = copy.deepcopy(self.produce_est)
        self.produce_est_sorted.sort(key=lambda x: x[0])
        self.wares_est = self.est_prices(type = BUYWARES) # value of wares
        self.wares_est_sorted = copy.deepcopy(self.wares_est)
        self.wares_est_sorted.sort(key=lambda x: x[0])

        if (self.verbose):
            print("Estimated value prices (value,colour):")
            print("[Produce Value] >",self.produce_est)
            print("[Wares Value] >",self.wares_est)

        actions = self.game.get_moves()
        select = self.order_moves(actions)

        choice = select[0][0]

        if AUCTION == choice:
            self.game.start_auction()
            return AUCTION

        elif BUYWARES == choice:
            self.game.buy_wares(select[0][2], select[0][3])
            return BUYWARES

        elif BUYPRODUCE == choice:
            self.game.buy_produce(select[0][2], self.game.auction_to_cart(select[0][3]))
            return BUYPRODUCE

        # Produce
        elif PRODUCE == choice:
            self.game.run_factory()
            return PRODUCE

        elif PASS == choice:
            if (self.game.verbose): print(">>> Player {} Passed turn <<<".format(self.playerID))
            return PASS

        else:
            raise Exception(f"Error unknown move by Best Agent, {select}")
            return False

    # estimates value of each action
    # currently doesnt support movement (just combine the 2, aka move+new option vs curr option+curr option)
    def order_moves(self,possible):
        moves = []
        if AUCTION in possible:
            #auction TODO maybe discount rate?
            moves.append((AUCTION,self.est_auction(self.game.player_cargo[self.playerID])))
        
        if BUYPRODUCE in possible:
            best_score = 0
            best_cart = []
            best_player = 0
            for p in range(self.game.NUM_PLAYERS):
                if p == self.playerID: continue
                cart = [0 for x in range(self.game.NUM_CONTAINERS)]
                est_score = 0
                for_sale = self.game.player_produce[p] # catalogue
                profits = []# profit for entire catalogue
                for c in range(self.game.NUM_CONTAINERS): # checks buys in order rather than by score card
                    for i in for_sale[c]:
                        #est_score = self.est_price(c,BUYPRODUCE)-i
                        est_score = self.wares_est[c][0]-i
                        profits.append((est_score,i,c)) # (est score, cost, colour)
                        # TODO possibly ignore profit < X

                profits.sort(key = lambda x: x[0], reverse=True)
                profits = profits[:self.game.get_numWarehouses()*2-self.game.get_numWares()] #space req
                cost = 0
                est_score = 0
                for x in range(len(profits)): # cash req, TODO assumes full spend cash
                    if (self.game.player_cash[self.playerID] < cost+profits[x][1]):
                        profits = profits[:x]
                        break
                    cost += profits[x][1]
                    est_score += profits[x][0]

                if est_score > best_score:
                    best_score = est_score
                    for x in profits:
                        cart[x[2]] += 1
                    best_cart = cart
                    best_player = p
            if best_cart != []: moves.append((BUYPRODUCE,best_score,best_player,best_cart))

        if BUYWARES in possible:
            best_score = -2
            best_cart = []
            best_player = 0
            for p in range(self.game.NUM_PLAYERS):
                if p == self.playerID: continue
                for_sale = self.game.player_wares[p]
                combi = self.game.get_combinations(for_sale,self.game.player_cash[self.playerID])
                for x in combi: 
                    # x = [cost, [(colour, qty),...]]
                    # assume value gained if auction would happens now
                    est_score = self.est_auction(self.game.cart_to_auction(x[1])) - x[0]
                    if est_score > best_score:
                        best_score = est_score
                        best_cart = x[1]
                        best_player = p
            if best_cart != []: moves.append((BUYWARES,best_score,best_player,best_cart))

        if PRODUCE in possible:
            best_score = 0
            prices = [0 for x in range(self.game.NUM_CONTAINERS)]
            # calc stuff added (assume all added)
            for x in range(self.game.NUM_CONTAINERS):
                price = self.produce_est[x][0]
                prices[x] = price
                best_score += self.game.player_factories[self.playerID][x]*price
            if (self.verbose): print(f"[Production] {best_score} Value")

            total = self.game.get_numProduce()
            cap = self.game.get_numFacts()
            if (total > cap):
                # calc priority and how much to drop
                count = total - cap

                # add stuff ignoring overflow
                produce = copy.deepcopy(self.game.player_produce[self.playerID])
                for x in range(self.game.NUM_CONTAINERS):
                    produce[x] = len(produce[x]) + self.game.player_factories[self.playerID][x]
                
                # minus stuff dropped
                reduce = 0
                for x in range(self.game.NUM_CONTAINERS):
                    colour = self.produce_est_sorted[x][1]
                    if (produce[colour] > count):
                        reduce += count*prices[colour]
                        break
                    else:
                        count -= produce[colour]
                        reduce += produce[colour]*prices[colour]
                if (self.verbose): print(f"[Production] Dropping {reduce}")
                best_score -= reduce

            if (self.game.player_cash[self.playerID] >= 1): moves.append((PRODUCE,best_score-1)) #fixed cost of 1
        moves.append((PASS, -0.01))

        moves.sort(key=lambda x: x[1],reverse=True)
        if (self.verbose): 
            for x in moves:
                print(f"{self.game.ACTION_KEY[x[0]]} {x[1:]}")
        return moves

    # input colour, output a price (historical price of WH and Fact)
    # TODO discount rate and ignore self bids and greedy(75 percentile)? 
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
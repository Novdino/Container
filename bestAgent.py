#from math import prod
import random
from agent import Agent
import math
import numpy as np

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

class BestAgent(Agent):
    def __init__(self,game,id):
        super().__init__(game,id)
        self.name = "BestAgent"
        self.verbose = False
        self.scorecard_est = self.est_score_cards() if not self.game.INFO_MODE == PERFECT else False

    # Best Agent move policy should give expected value
    # bid policy perfect info calculate (no discount)
    # repricing policy is product:1, warehouse:2
    def make_move(self, MOVE = -1):
        actions = self.game.get_moves()
        if MOVE in actions:
            actions = [MOVE] # only choose from this
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

        elif PRODUCE == choice:
            self.game.run_factory()
            return PRODUCE

        elif PASS == choice:
            if (self.game.verbose): print(">>> Player {} Passed turn <<<".format(self.playerID))
            return PASS

        else:
            raise Exception("Error unknown move by Best Agent")
            return False

    # estimates value of each action
    # currently doesnt support movement (just combine the 2, aka move+new option vs curr option+curr option)
    def order_moves(self,possible):
        moves = []
        if AUCTION in possible:
            moves.append((AUCTION,self.est_auction(self.game.player_cargo[self.playerID])))
            if (self.verbose): print(f"Auction, {moves[0][1]}")
        
        if BUYPRODUCE in possible:
            best_score = 0
            best_cart = []
            best_player = 0
            for p in range(self.game.NUM_PLAYERS):
                if p == self.playerID: continue
                cart = [0 for x in range(self.game.NUM_CONTAINERS)]
                est_score = 0
                for_sale = self.game.player_produce[p] 
                for c in range(self.game.NUM_CONTAINERS): # TODO checks buys in order rather than by score card
                    for i in for_sale[c]: # red colour [1,2,2], priced at 1,2,2
                        # since sell at 2, only buy at 1 + never exceed capacity
                        if i == 1 and (sum(cart)+self.game.get_numWares()) < self.game.get_numWarehouses()*2 and sum(cart) < self.game.player_cash[self.playerID]:
                            est_score += 1
                            cart[c] += 1
                if (self.verbose): print(f"buyprod, cart {cart}, est_score {est_score}")
                if est_score > best_score:
                    best_score = est_score
                    best_cart = cart
                    best_player = p        
            if best_cart != []: moves.append((BUYPRODUCE,best_score,best_player,best_cart))
            if (self.verbose): print(f"Buy Produce, {best_score}, cart {best_cart} from {best_player}")

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
                    if (self.verbose): print(f"buywares, cart {x}, est_score {est_score},{self.est_auction(self.game.cart_to_auction(x[1]))}-{x[0]}")
            if best_cart != []: moves.append((BUYWARES,best_score,best_player,best_cart))

            if (self.verbose): print(f"Buy Wares, {best_score}, cart {best_cart} from {best_player}")

        if PRODUCE in possible:
            # always sells at 1
            if (self.game.get_numProduce() > self.game.get_numFacts()):
                #overflow of goods
                best_score = self.game.get_numFacts()*2 - self.game.get_numProduce()
            else:
                best_score = self.game.get_numFacts()
            if (self.game.player_cash[self.playerID] >= 1): moves.append((PRODUCE,best_score-1)) # -1 cost to produce
            
            if (self.verbose): print(f"Produce, {best_score-1}")

        moves.append((PASS, 0))

        moves.sort(key=lambda x: x[1],reverse=True)
        return moves
    
    def est_endgame(self):
        if self.game.infinity_mode:
            return self.game.infinity_mode

        # rate of container decline based on 
        # num factories and % chance to take the produce action
        decline = [0 for x in range(self.game.NUM_CONTAINERS)] # expected decline in amt of containers per turn
        for p in range(self.game.NUM_PLAYERS):
            if len(self.game.history[p]) != 0:
                pa = self.game.history[p].count(PRODUCE)/len(self.game.history[p])
                for c in range(self.game.NUM_CONTAINERS):
                    decline[c] += pa*self.game.player_factories[p][c]
        
        max = 200-self.game.turn_count # max 100 turns empirically
        for c in range(self.game.NUM_CONTAINERS):
            if decline[c] != 0:
                decline[c] = self.game.supply[c]/decline[c]
                if decline[c] < max:
                    max = decline[c]

        return max

    # HOW MUCH IS CONTIANERS ACTUALLY WORTH TO PLAYER
    # product = [x for each colour]
    # score_card = [[player 0 container values],...]
    def containers_score(self, player, product, score_card=False):
        points = score_card if score_card else self.game.player_cards
        return sum(np.multiply(np.array(product), np.array(points[player])))

    def get_bid(self, product):
        self_value = min(self.containers_score(self.playerID,product),self.game.player_cash[self.playerID])
        if (self.verbose): 
            print("[Bid] ", product)
            print("[Bid] Value to me > ", self_value)
        
        best_bidder = 0
        for i in range(self.game.NUM_PLAYERS):
            if i != self.playerID and i != self.game.active_player:
                bidder_value = min(self.containers_score(i,product,self.scorecard_est),self.game.player_cash[i])
                if (self.verbose): print(f"[Bid]  Player {i} > {bidder_value} |",self.containers_score(i,product,self.scorecard_est),self.game.player_cash[i])

                if bidder_value > best_bidder:
                    best_bidder = bidder_value

        owner_value = self.containers_score(self.game.active_player,product,self.scorecard_est)
        if (self.verbose): print(f"[Bid]  Seller Player {self.game.active_player} > {owner_value}")
        return min(self_value, max(best_bidder, round(owner_value/2)))

    # gives estimated score card for each player from the auction log
    # [turn count, sum], weighted = sum/turn counts
    def est_score_cards(self):
        scores = [[[0,0] for x in range(self.game.NUM_CONTAINERS)] for y in range(self.game.NUM_PLAYERS)]
        for x in self.game.auction_log:
            # x = (turn0, price1, bundle of product2, seller3, buyer4, [max bids by each player])
            # considering winning bid only for buyer
            # maybe lower weights for non winning bids?
            if x[4] != x[3] and x[3] != self.playerID:
                total = sum(x[2])
                for c in range(self.game.NUM_CONTAINERS):
                    num = x[2][c]
                    if (num != 0):
                        scores[x[4]][c][0] += x[0] # turn 
                        scores[x[4]][c][1] += x[0]*x[1]*num/total # x % ofCart

        # Calc score
        for p in range(self.game.NUM_PLAYERS):
            for c in range(self.game.NUM_CONTAINERS):
                try:
                    scores[p][c] = scores[p][c][1]/scores[p][c][0]
                except:
                    scores[p][c] = 5 #avg value if no info

        # fit to closest infoset (MSE)
        if (self.game.INFO_MODE == SEMI_PERFECT):
            cards = self.game.generate_card(GET_COMBI=True)
            cards.remove(self.game.player_cards[self.playerID]) # cant be my own card
            out = [[] for x in range(self.game.NUM_PLAYERS)]
            for p in range(self.game.NUM_PLAYERS):
                if p == self.playerID: 
                    out[p] = self.game.player_cards[self.playerID]
                    continue

                for c in cards:
                    total = 0
                    for i in range(self.game.NUM_CONTAINERS):
                        total += (c[i]-scores[p][i])**2
                    mse = total/(len(cards)-1)
                    out[p].append((mse,c))
                
                out[p].sort(key=lambda x: x[0])

            # greedy choose if fit (assumes no duplicates)
            for p in range(self.game.NUM_PLAYERS-1):
                best_mse = 9999
                best_player = -1
                best_card = -1
                for i in range(self.game.NUM_PLAYERS):
                    if (type(out[i][0]) == int): # already set
                        continue
                    else:
                        while (not out[i][0][1] in cards):
                            out[i].pop(0)
                        if (out[i][0][0] < best_mse):
                            best_mse = out[i][0][0]
                            best_player = i
                            best_card = out[i][0][1]
                cards.remove(best_card)
                out[best_player] = best_card                

        else:
            out = scores

        if (self.verbose): print(f"[Score] Predict vs Guess vs Actual:\n {scores} \n{out}\n{self.game.player_cards}")

        return out
    
    # esitmate best bid if player hosts auction
    def est_auction(self,product):
        self_value = min(self.containers_score(self.playerID,product),self.game.player_cash[self.playerID])
        if (self.verbose): 
            print("[Auction] ", product)
            print("[Auction] Value to me > ", self_value)

        best_bidder = 0
        for i in range(self.game.NUM_PLAYERS):
            if i != self.playerID:
                bidder_value = min(self.containers_score(i,product,self.scorecard_est),self.game.player_cash[i])
                if (self.verbose): 
                    print(f"[Auction] Player {i} > {bidder_value} |", self.containers_score(i,product,self.scorecard_est),self.game.player_cash[i])

                if bidder_value > best_bidder:
                    best_bidder = bidder_value
        if (self.verbose): print("[Auction] Value: ",max(best_bidder if self.game.monopoly_mode else best_bidder*2, self_value))
        if (self.game.monopoly_mode): return max(best_bidder, self_value)
        else: return max(best_bidder*2, self_value)

    def factory_reprice(self):
        goods = self.game.player_produce[self.playerID]

        #drop overflow
        total = self.game.get_numProduce()
        cap = self.game.get_numFacts()
        count = total - cap*2
        drop = []
        if (count > 0):
            drop = random.sample([x for x in range(total)],count)
            if (self.game.verbose): print("Dropping ",drop, goods)

        #reprice
        i = 0
        for type in range(len(goods)):
            for item in range(len(goods[type])-1,-1,-1):
                if (i in drop): del goods[type][item]
                else: goods[type][item] = 1 # sets price to 1
                i += 1
            goods[type].sort()

    def warehouse_reprice(self,player,cart):
        goods = self.game.player_wares[self.playerID]

        #drop overflow
        total = self.game.get_numWares()
        cap = self.game.get_numWarehouses()
        count = total - cap*2
        drop = []
        if (count > 0):
            drop = random.sample([x for x in range(total)],count)
            if (self.game.verbose): print("Dropping ",drop, goods)

        #reprice
        i = 0
        for type in range(len(goods)):
            for item in range(len(goods[type])-1,-1,-1):
                if (i in drop): del goods[type][item]
                else: goods[type][item] = 2 # sets price to 2
                i += 1
            goods[type].sort()
        
    def accept_bid(self,bid,product,buyer,bids):
        bid_value = bid*2 if not self.game.monopoly_mode else bid

        # value offered > amt cash on hand || container _score - cost to self buy
        if (bid_value > min(self.containers_score(self.playerID,product,self.scorecard_est)-bid,self.game.player_cash[self.playerID])):
            return True
        else:
            return False
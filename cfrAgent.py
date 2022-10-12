from random2Agent import RandomAgent
from mctsAgent import MCTSNode,MCTSAgent,ISMCTSNode
import CFRNode
import random
import numpy as np
import copy
import pickle

PRODUCE = 0
BUYPRODUCE = 1
BUYWARES = 2
AUCTION = 3
PASS = 4
SAILSEA = 5
BUYFACT = 6
BUYWAREHOUSE = 7
ACTION_KEY = ["Produce","Buy Produce", "Buy Wares","Auction","Pass","Sail Sea","Buy Fact","Buy Warehouse"]

PERFECT = 0 # can see score cards
SEMI_PERFECT = 1 # info set limited
HIDDEN = 2

# GLOBAL STRATEGY PLAYED BY AGENT
fd = open("./CFRStrategies/BaseMCCFR_20000.pickle", 'rb')
STRATEGIES = pickle.load(fd)
fd.close()
print(STRATEGIES["Fprice"])
print(STRATEGIES["Wprice"])
#STRATEGIES = {} # NO STRATEGY

class CFRAgent(MCTSAgent):
    def __init__(self,game,id):
        super().__init__(game,id)
        self.name = "CFRAgent"
        self.verbose = False

    def make_move(self):
        infoset = CFRNode.abstract_game(self.game,self.playerID)
        if infoset in STRATEGIES and STRATEGIES[infoset].explored > 1:
            #strategy = STRATEGIES[infoset].get_average_strategy() # EQUILIBRIUM
            strategy = STRATEGIES[infoset].get_strategy() # REGRET STRATEGY
            move = STRATEGIES[infoset].get_action(strategy, valid = self.game.get_moves())
            if self.verbose: print(f"Seen: {infoset} Action {move} {strategy}")

            if move == BUYPRODUCE or move == BUYWARES:
                highest_node = None
                highest_regret = -100
                highest_seller = None
                for x in range(1,self.game.NUM_PLAYERS):
                    seller = (self.game.active_player+x)%self.game.NUM_PLAYERS
                    if move == BUYPRODUCE: for_sale = self.game.player_produce[seller]
                    else: for_sale = self.game.player_wares[seller]
                    if self.game.is_combinations(for_sale,self.game.player_cash[self.game.active_player]): # can be brought from
                        infoset = CFRNode.abstract_buy(self.game,self.game.active_player,seller, WH=(move == BUYWARES))
                        if infoset in STRATEGIES:
                            node = STRATEGIES[infoset]
                            if max(node.regret_sum) > highest_regret: 
                                highest_node = node
                                highest_regret = max(node.regret_sum)
                                highest_seller = seller
                        else:
                            return super().make_move(MOVE=move)

                strategy = highest_node.get_strategy()
                action = highest_node.get_action(strategy,valid = CFRNode.get_valid_buy(self.game, highest_node.infoset, for_sale))
                carts = CFRNode.get_actions_buy_infoset(highest_node.infoset,CFRNode.get_score_colour_order(self.game))
                
                if move == BUYWARES:
                    self.game.buy_wares(highest_seller,carts[action])
                    return BUYWARES
                else:
                    self.game.buy_produce(highest_seller,carts[action])
                    return BUYPRODUCE
            
            if move == PRODUCE:
                # CFR doesnt have a pass action, thus it defaults to the least bad option which is usually produce
                # this prevents over production
                if self.game.get_numProduce() == sum(self.game.player_factories[self.playerID])*2:
                    return PASS

            return super().make_move(MOVE=move)
        else: 
            #if self.verbose: print(f"Not Seen: {infoset}")
            return super().make_move()

    def shufflePrices(self, goods, cap, MIN, MAX, WH=False):
        if "Wprice" if WH else "Fprice" in STRATEGIES:
            node = STRATEGIES["Wprice" if WH else "Fprice"]
            i = node.get_action(node.get_strategy())
            order = CFRNode.get_score_colour_order(self.game)
            pricing = CFRNode.getPricingStrategy(i, order)

            if WH: #buy produce
                drops = self.game.get_numWares() - cap*2
                self.game.player_wares[self.game.active_player] = CFRNode.set_pricing(goods,pricing,BUYPRODUCE,drops)
            else: #produce
                drops = self.game.get_numProduce() - cap*2
                self.game.player_produce[self.game.active_player] = CFRNode.set_pricing(goods,pricing,PRODUCE,drops)
        else: super().shufflePrices(goods, cap, MIN, MAX, WH)

    def create_CFRbid_root(self, infoset, upper):
        #strategy = STRATEGIES[infoset].get_average_strategy()
        strategy = STRATEGIES[infoset].get_strategy()
        bid_bucket = STRATEGIES[infoset].get_action(strategy)
        BID_RANGE = CFRNode.unabstract_auction_cash(self.game.player_cash[self.playerID],upper,bid_bucket)

        #FROM MCTS AGENT (CHANGED CHILD BID CREATION)
        bids = np.full(self.game.NUM_PLAYERS,-1)
        root = self.createRoot(self.game)
        for bid in BID_RANGE: # manually create children
            bids[self.playerID] = bid
            next_game = copy.deepcopy(root.game)
            next_game.start_auction(starting_bids=bids) # start auction where I bid X
            next_game.make_move(MOVE = AUCTION)
            root.children_nodes.append(root.create_child(next_game,bid))
        return root
    
    def get_bid(self, product):
        infoset, upper = CFRNode.abstract_auction(self.game,self.playerID)
        if infoset in STRATEGIES:
            root = self.create_CFRbid_root(infoset, upper)
            return self.mcts_get_bid(product, root)

        else:
            #if self.verbose: print(f"Not Seen: {infoset}")
            root = self.create_bid_root(product)
            return self.mcts_get_bid(product, root)
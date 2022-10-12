from distutils.log import info
import numpy as np
import random #import random, shuffle, randint, choice
import time
from numpy.random import choice
from gameMulti import Game
import copy
import pickle
from gameMulti import Game
import CFRNode

PRODUCE = 0
BUYPRODUCE = 1
BUYWARES = 2
AUCTION = 3
PASS = 4
SAILSEA = 5
BUYFACT = 6
BUYWAREHOUSE = 7
ACTION_KEY = ["Produce","Buy Produce", "Buy Wares","Auction","Pass","Sail Sea","Buy Fact","Buy Warehouse"]
PRICING = 8
GENERAL = 9
BUY = 10

PERFECT = 0 # can see score cards
SEMI_PERFECT = 1 # info set limited
HIDDEN = 2

PRODUCE_PRICES = np.array([1,2,3,4]) # NODE PRICES TO ACTUAL PRICES
WARES_PRICES = np.array([2,3,4,5])

# NODE PRICING (ALSO CHANGE IN CFRNODE)
NODE_PRICES = [[3,3,3],[0,0,0],[0,1,2],[1,2,3]] #blueprints
#NUM_REPRICES = 4 # 3 COLOURS, 3 PRICES
#NODE_PRICES = [[]] + list(np.ndindex(NUM_REPRICES, NUM_REPRICES, NUM_REPRICES)) 

# CFR CONFIGS FOR TRAINING
MAX_DEPTH_MOD = 1 # CHANGE THIS AFTER 10000 ITERATIONS
GENERAL_MAX_DEPTH = 10*MAX_DEPTH_MOD # BRANCHING ONLY FOR COUNTING PERSPECTIVE PLAYER
AUCTION_MAX_DEPTH = 5*MAX_DEPTH_MOD
BUY_MAX_DEPTH = 5*MAX_DEPTH_MOD
PRICE_MAX_DEPTH = 20

GENERAL_MAX_EXPLORE = 2 # PER ITERATION EXPLORED LIMIT 
AUCTION_MAX_EXPLORE = 2
BUY_MAX_EXPLORE = 5
PRICE_MAX_EXPLORE = 10

SEARCH_LIMIT = 0.001 # if action falls below the threshold, only search SEARCH_PROBA% of the time 
SEARCH_PROBA = 0.95

class CFRTrainer:
    def __init__(self):
        self.nodeMap = {}
        self.iters = 0

    # TRAINING FUNCTIONS
    def train(self, n_iterations=10000, display = False, config = {}, nodeMap = {}, iters = 0, depth = False):
        self.iters = iters
        self.nodeMap = nodeMap

        # init pricing nodes
        n_actions = len(NODE_PRICES) # blueprint strats [random, lowest, asc, asc2]
        if "Fprice" not in self.nodeMap: self.nodeMap["Fprice"] = CFRNode.CFRNode("Fprice",n_actions)
        if "Wprice" not in self.nodeMap: self.nodeMap["Wprice"] = CFRNode.CFRNode("Wprice",n_actions)
        
        # timers
        time1 = time.time()
        time_end = time.time()
        timerbox = [0,0,0,0]
        total_timerbox = [0,0,0,0]

        for _ in range(n_iterations):
            if _%100 == 0: 
                print(f"{_}/{n_iterations} {abs(time1 - time.time())/60} mins {timerbox}")
                for x in range(4):
                    total_timerbox[x] += timerbox[x]
                timerbox = [0,0,0,0]
                time1 = time.time()
            if (_+1)%1000 == 0: 
                print(f"Creating Save Point")
                fd = open(f'./MCCFR_{self.iters+1}.pickle', 'wb') 
                pickle.dump(self.nodeMap, fd)
                print(f"Total States : {len(self.nodeMap.items())} {total_timerbox}")

            self.iters += 1
            # Forgets bad strategies half way through and resets exploration
            if self.iters == n_iterations // 2:
                for _, v in self.nodeMap.items():
                    v.clear_strategy()

            self.ref_player = random.randint(0,config["num_players"]-1)
            ai = ["BestAgent","BestAgent","BestAgent"]
            #ai[self.ref_player] = "MCTSAgent" # if only general nodes
            ai[self.ref_player] = "BestAgent" # if full only affect selfbuy
            self.game = Game(**config,ai=ai)
            
            if self.iters > 2000 or depth: # start game midway
                turns = random.randint(0,40)
                for x in range(turns):
                    if self.game.game_over: break
                    
                    infoset = CFRNode.abstract_game(self.game,self.ref_player)
                    node = self.get_node(infoset)
                    strategy = node.get_strategy() #!possbily redundant
                    action = node.get_action(strategy,valid = self.game.get_moves())

                    # play against self
                    self.game = self.play_current_strategy(self.game,action)

                    # play against blueprint
                    # self.game = self.next_gameState(self.game)
                    
                if self.game.game_over: continue

            timer = time.time()
            self.cfr(self.game,0, GENERAL) # depth = 0
            timerbox[0] += timer - time.time()
            
            timer = time.time()
            self.cfr(self.game,0, AUCTION)
            timerbox[1] += timer - time.time()
            
            timer = time.time()
            self.cfr(self.game,0, BUY)
            timerbox[2] += timer - time.time()
            
            timer = time.time()
            self.cfr(self.game,0, PRICING) 
            timerbox[3] += timer - time.time()

        if display:
            CFRNode.display_results(self.nodeMap,number = display)
            print(f"Total States : {len(self.nodeMap.items())} {abs(time_end - time.time())/60} mins")

    # performs CFR for 1 type of action, for 1 player
    # TYPE is what cfr is currenetly being trained
    def cfr(self, gamestate, depth, TYPE):
        if gamestate.game_over: return gamestate.final_score[self.ref_player]
        infoset = CFRNode.abstract_game(gamestate,self.ref_player)

        # GET GENERAL STRATEGY
        node = self.get_node(infoset)
        strategy = node.get_strategy() #!possbily redundant
        action = node.get_action(strategy,valid = gamestate.get_moves())
        if gamestate.active_player == self.ref_player:
            #if infoset.startswith("0/0/0/0"): return -100
            # Counterfactual utility per action.
            if TYPE == GENERAL:
                if node.explored > self.iters*GENERAL_MAX_EXPLORE: return self.cfr(self.play_current_strategy(gamestate,action), depth, TYPE)
                if depth >= GENERAL_MAX_DEPTH: return gamestate.final_scoring()[self.ref_player]
                action_utils = np.zeros(node.n_actions)
                for action in gamestate.get_moves(): # make all possible actions
                    if action != PASS: 
                        if strategy[action] <= SEARCH_LIMIT and random.random() <= SEARCH_PROBA: #dont search low
                            action_utils[action] = 0 
                            continue
                        action_utils[action] = self.cfr(self.play_current_strategy(gamestate,action), depth+1, TYPE)
                util = np.sum(action_utils * strategy)
                regrets = action_utils - util
                node.regret_sum += regrets
                node.explored += 1
                return util
            elif TYPE == BUY and (action == BUYWARES or action == BUYPRODUCE):
                if depth >= BUY_MAX_DEPTH: return gamestate.final_scoring()[self.ref_player]
                return self.buy_cfr(gamestate, depth+1, action, TYPE)
            elif TYPE == PRICING and (action == PRODUCE or action == BUYPRODUCE):
                if depth >= PRICE_MAX_DEPTH: return gamestate.final_scoring()[self.ref_player]
                return self.pricing_cfr(gamestate, depth+1, action, TYPE)
            else: # training auction
                return self.cfr(self.play_current_strategy(gamestate,action), depth, TYPE)
        else:
            # not updating this player, just take action according to current
            # self play
            if TYPE == AUCTION and action == AUCTION: # what to bid in other player's auction
                if depth >= AUCTION_MAX_DEPTH: return gamestate.final_scoring()[self.ref_player]
                return self.auction_cfr(gamestate, depth+1, TYPE)

            # play against self
            return self.cfr(self.play_current_strategy(gamestate,action), depth, TYPE)

            # play against blueprint
            # return self.cfr(self.next_gameState(gamestate), depth, TYPE)

    def auction_cfr(self, gamestate, depth, TYPE):
        # Counterfactual utility per action.
        infoset, upper = CFRNode.abstract_auction(gamestate,self.ref_player)
        node = self.get_node(infoset,TYPE=AUCTION)
        if node.explored > self.iters*AUCTION_MAX_EXPLORE: return self.cfr(self.play_current_strategy(gamestate,AUCTION), depth, TYPE)

        strategy = node.get_strategy()
        action_utils = np.zeros(node.n_actions)
        bids = self.get_bids(gamestate)
        for bid_bucket in range(5): # 5 bid buckets
            bid = choice(CFRNode.unabstract_auction_cash(gamestate.player_cash[self.ref_player],upper,bid_bucket))
            bids[self.ref_player] = bid
            action_utils[bid_bucket] = self.cfr(self.next_gameState(gamestate,AUCTION,args=[bids]),depth, TYPE)
        
        util = np.sum(action_utils * strategy)
        regrets = action_utils - util
        node.regret_sum += regrets
        node.explored += 1
        return util

    # 2 types BUYPRODUCE AND BUY WARES
    def buy_cfr(self, gamestate, depth, action, TYPE):
        # cfr all other players but only pass up best (since player would choose best)
        best_util = -100 
        for x in range(1,gamestate.NUM_PLAYERS):
            seller = (self.ref_player+x)%gamestate.NUM_PLAYERS
            infoset = CFRNode.abstract_buy(gamestate,self.ref_player,seller, WH=(action == BUYWARES))
            node = self.get_node(infoset,TYPE=BUY)
            if not node: continue # this player has nothing to sell
            strategy = node.get_strategy()
            action_utils = np.zeros(node.n_actions)

            if action == BUYWARES: goods = gamestate.player_wares[seller]
            else: goods = gamestate.player_produce[seller]
            carts = CFRNode.get_actions_buy_infoset(infoset,CFRNode.get_score_colour_order(gamestate))

            if node.explored > self.iters*BUY_MAX_EXPLORE: # no depth -1 since will lead to uneven branching
                i = node.get_action(strategy,valid = CFRNode.get_valid_buy(gamestate, node.infoset, goods))
                util = self.cfr(self.play_current_strategy(gamestate,action, args=[seller,carts[i]]), depth, TYPE)
                if (util>best_util): best_util = util
                continue

            for i in CFRNode.get_valid_buy(gamestate, node.infoset, goods): # make valid actions
                if strategy[i] <= SEARCH_LIMIT and random.random() <= SEARCH_PROBA: #dont search low
                    action_utils[i] = 0 
                    continue
                if action == BUYPRODUCE: # need reprice
                    action_utils[i] = self.cfr(self.play_current_strategy(gamestate,action, args=[seller,carts[i]]), depth, TYPE)
                else:
                    action_utils[i] = self.cfr(self.next_gameState(gamestate,action, args=[seller,carts[i]]), depth, TYPE)
            
            util = np.sum(action_utils * strategy)
            if (util>best_util): best_util = util
            regrets = action_utils - util
            node.regret_sum += regrets
            node.explored += 1
        return best_util

    # could either be from either produce/buy produce
    def pricing_cfr(self, gamestate, depth, action, TYPE):
        # GET NEW STORE
        node = self.get_node("Fprice" if action == PRODUCE else "Wprice",TYPE=PRICING)
        if node.explored > self.iters*PRICE_MAX_EXPLORE: return self.cfr(self.play_current_strategy(gamestate, action), depth, TYPE)

        order = CFRNode.get_score_colour_order(gamestate)
        if action == PRODUCE:
            gamestate.run_factory(-1)
            store = gamestate.player_produce[gamestate.active_player]
            drops = gamestate.get_numProduce() - gamestate.get_numFacts()*2

        elif action == BUYPRODUCE:
            # GET BUY PRODUCE ACTION
            highest_node, highest_seller = self.get_buy_infoset(gamestate, BUYPRODUCE)
            for_sale = gamestate.player_produce[highest_seller] # whats for sale
            strategy = highest_node.get_strategy()
            valid_branches = CFRNode.get_valid_buy(gamestate, highest_node.infoset, for_sale)
            move = highest_node.get_action(strategy,valid = valid_branches)
            carts = CFRNode.get_actions_buy_infoset(highest_node.infoset,order)
            
            gamestate.buy_produce(highest_seller,carts[move],-1)
            store = gamestate.player_wares[gamestate.active_player]
            drops = gamestate.get_numWares() - gamestate.get_numWarehouses()*2

        else: raise Exception("Pricing cfr incorrect action type")
        
        # GET PRICING NODE
        strategy = node.get_strategy()
        action_utils = np.zeros(node.n_actions)

        for i in range(len(NODE_PRICES)):
            if strategy[i] <= SEARCH_LIMIT and random.random() <= SEARCH_PROBA: #dont search low
                action_utils[i] = 0 
                continue

            next_game = copy.deepcopy(gamestate)
            pricing = CFRNode.getPricingStrategy(i, order) # convert scorcecard back to game
            if action == PRODUCE: next_game.player_produce[next_game.active_player] = CFRNode.set_pricing(store,pricing,action,drops)
            else: next_game.player_wares[next_game.active_player] = CFRNode.set_pricing(store,pricing,action,drops)
            next_game.make_move(MOVE=action) # tell game agent has made action
            action_utils[i] = self.cfr(gamestate, depth, TYPE)

        util = np.sum(action_utils * strategy)
        regrets = action_utils - util
        node.regret_sum += regrets
        node.explored += 1
        return util

    def get_node(self, infoset, TYPE = -1):
        if infoset not in self.nodeMap:
            if TYPE == AUCTION: n_actions = 5
            elif TYPE == BUY: 
                if infoset[-3:] == "|--": return None # nothing to buy
                n_actions = len(CFRNode.get_actions_buy_infoset(infoset))
            elif TYPE == PRICING: 
                raise Exception("No pricing node found") # shoulld be initialised
                n_actions = len(NODE_PRICES) # blueprint strats [random, lowest, asc, asc2]
                info_set = CFRNode.CFRNode(infoset,n_actions)
                self.nodeMap["price"] = info_set
                return info_set
            else: n_actions = 4 # general strategy
            
            info_set = CFRNode.CFRNode(infoset,n_actions)
            self.nodeMap[infoset] = info_set
            #print(f"New State {infoset}")
            return info_set
        return self.nodeMap[infoset]

    # returns an array of $ bids players would have made following the current strategy
    def get_bids(self, gamestate):
        bids = np.full(gamestate.NUM_PLAYERS,-1)

        for x in range(gamestate.NUM_PLAYERS): # infostate from each player's perspective
            if x == gamestate.active_player: continue # host doesnt bid

            infoset, upper = CFRNode.abstract_auction(gamestate,x)
            node = self.get_node(infoset,TYPE=AUCTION)
            strategy = node.get_strategy()
            bid_bucket = node.get_action(strategy)
            BIDS = CFRNode.unabstract_auction_cash(gamestate.player_cash[x],upper,bid_bucket)
            bid = choice(BIDS)
            bids[x] = bid
        
        return bids

    # given a game state and a type
    # choose a split on who to buy and return infoset
    def get_buy_infoset(self, gamestate, action):
        highest_node = None
        highest_regret = -100
        highest_seller = None
        for x in range(1,gamestate.NUM_PLAYERS):
            seller = (gamestate.active_player+x)%gamestate.NUM_PLAYERS
            if action == BUYPRODUCE: for_sale = gamestate.player_produce[seller]
            else: for_sale = gamestate.player_wares[seller]
            if gamestate.is_combinations(for_sale,gamestate.player_cash[gamestate.active_player]): # can be brought from
                infoset = CFRNode.abstract_buy(gamestate,gamestate.active_player,seller, WH=(action == BUYWARES))
                node = self.get_node(infoset,TYPE=BUY)
                if max(node.regret_sum) > highest_regret: 
                    highest_node = node
                    highest_regret = max(node.regret_sum)
                    highest_seller = seller
        return highest_node, highest_seller

    # advance game state by action according to current strategy
    def play_current_strategy(self, gamestate, action, args = -1):
        if action == AUCTION:
            bids = self.get_bids(gamestate) # oso updates strategy sum
            return self.next_gameState(gamestate,AUCTION,args=[bids])
        elif action == BUYWARES:
            # choose node containing action with the highest regret_sum
            highest_node, highest_seller = self.get_buy_infoset(gamestate, action)
            for_sale = gamestate.player_wares[highest_seller]
            strategy = highest_node.get_strategy()
            action = highest_node.get_action(strategy,valid = CFRNode.get_valid_buy(gamestate, highest_node.infoset, for_sale))
            carts = CFRNode.get_actions_buy_infoset(highest_node.infoset,CFRNode.get_score_colour_order(gamestate))

            return self.next_gameState(gamestate, BUYWARES, args=[highest_seller,carts[action]])
        elif action == BUYPRODUCE:
            if args == -1: # dont know what to buy
                highest_node, highest_seller = self.get_buy_infoset(gamestate, action)
                for_sale = gamestate.player_produce[highest_seller]
                strategy = highest_node.get_strategy()
                valid_actions = CFRNode.get_valid_buy(gamestate, highest_node.infoset, for_sale)
                action = highest_node.get_action(strategy,valid = valid_actions)
                carts = CFRNode.get_actions_buy_infoset(highest_node.infoset,CFRNode.get_score_colour_order(gamestate))
                buying_produce = carts[action]
            else: # know what to buy
                highest_seller = args[0]
                buying_produce = args[1]

            # find what to price
            next_game = copy.deepcopy(gamestate)
            next_game.buy_produce(highest_seller,buying_produce,-1)
            store = next_game.player_wares[next_game.active_player]
            drops = next_game.get_numWares() - next_game.get_numWarehouses()*2
            node = self.get_node("Wprice",TYPE=PRICING)
            strategy = node.get_strategy()
            i = node.get_action(strategy)
            order = CFRNode.get_score_colour_order(gamestate)
            pricing = CFRNode.getPricingStrategy(i, order)

            next_game.player_wares[next_game.active_player] = CFRNode.set_pricing(store,pricing,action,drops)
            next_game.make_move(MOVE=BUYPRODUCE) # tell game agent has made action
            return next_game
     
        elif action == PRODUCE:
            next_game = copy.deepcopy(gamestate)
            next_game.run_factory(-1)
            store = next_game.player_produce[next_game.active_player]
            drops = next_game.get_numProduce() - next_game.get_numFacts()*2
            node = self.get_node("Fprice",TYPE=PRICING)
            strategy = node.get_strategy()
            i = node.get_action(strategy)
            order = CFRNode.get_score_colour_order(gamestate)
            pricing = CFRNode.getPricingStrategy(i, order)

            next_game.player_produce[next_game.active_player] = CFRNode.set_pricing(store,pricing,action,drops)
            next_game.make_move(MOVE=PRODUCE) # tell game agent has made action
            return next_game
        else:
            return self.next_gameState(gamestate,action)

    # advance game state by action according to args or default
    def next_gameState(self, gamestate, action=-1, args = -1):
        next_game = copy.deepcopy(gamestate)
        if action == AUCTION and args != -1:
            next_game.start_auction(starting_bids=args[0]) # start auction with these bids
            next_game.make_move(MOVE = AUCTION)
            return next_game
        elif (action == BUYWARES or action == BUYPRODUCE) and args != -1:
            player = args[0]
            cart = args[1]
            if action == BUYWARES:
                next_game.buy_wares(player, cart)
            else:
                next_game.buy_produce(player, cart)
            next_game.make_move(MOVE = action)
            return next_game
        elif action != -1:
            next_game.players[next_game.active_player].make_move(MOVE=action) # tell agent to make action
            next_game.make_move(MOVE=action) # tell game agent has made action
            return next_game
        else:
            action = next_game.players[next_game.active_player].make_move()
            next_game.make_move(MOVE=action)
            return next_game

if __name__ == "__main__":
    config = {
        "review" : False, # show graphical ui
        "verbose" : False, # print game info to console
        "anticheat" : False, # checks if players cheat every turn
        "logfile": "", # name of file to write to
        
        # Gamemodes
        "monopoly_mode": True,
        "infinity_mode": 100,
        "infomation": PERFECT,
        #"infomation": SEMI_PERFECT,

        # Starting Conditions
        "num_players":3,
        "NUM_CONTAINERS":3,
        "STARTING_FACTS":2,
        "STARTING_WH":2,
        "STARTING_CAPTIAL":10,
    }

    # INITIAL STRATEGY
    fd = open("./ExpandedCFR/MCCFR_16000.pickle", 'rb') 
    STRATEGIES = pickle.load(fd) 
    #STRATEGIES = {}
    
    trainer = CFRTrainer()
    trainer.train(n_iterations=10000, display=10, config = config,iters = 0, nodeMap=STRATEGIES, depth = False)
    print(trainer.nodeMap["Fprice"])
    print(trainer.nodeMap["Wprice"])
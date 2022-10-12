import math
from random2Agent import RandomAgent
import copy
import numpy as np
from itertools import permutations,combinations_with_replacement,product


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

NUM_ROLLOUT_PER_ITER = 10
ROLLOUT_BID_MOD = 5
NUM_ITER = 50
        
class MCTSNode(object):
    def __init__(self,game,parent,move):
        self.game = game
        self.children_nodes = []
        self.move = move # move that got here from parent
        self.parent = parent
        self.ucb_score = math.inf
        self.LAMBDA = 2*20 # exploration constant, increase for more exploration
        self.num_sims = 0

        self.RAVE = True
        self.amaf_num_sims = 0 
        self.b = 100

    # wrapper for creating new node
    def create_child(self, game, move):
        return MCTSNode(game,self,move)

    def make_children(self,MOVE=-1):
        if self.game.game_over:
            self.children_nodes = -1
        else:
            if MOVE == -1: moves = self.game.get_moves()
            else: moves = [MOVE]
            #print(self.game.active_player)

            if AUCTION in moves:
                next_game = copy.deepcopy(self.game)
                next_game.start_auction()
                next_game.make_move(MOVE = AUCTION)
                node = self.create_child(next_game,AUCTION)
                self.children_nodes.append(node)
                
            if BUYWARES in moves:
                for p in self.game.who_buyable(self.game.player_wares):
                    for x in self.game.get_combinations(self.game.player_wares[p],self.game.player_cash[self.game.active_player]):
                        next_game = copy.deepcopy(self.game)
                        next_game.buy_wares(p, x[1])
                        next_game.make_move(MOVE = BUYWARES)
                        node = self.create_child(next_game,(BUYWARES,p,x[1]))
                        self.children_nodes.append(node)
            
            if BUYPRODUCE in moves:
                # dont over buy
                #free_space = self.game.get_numWarehouses()*2 - self.game.get_numWares()
                for p in self.game.who_buyable(self.game.player_produce):
                    for x in self.game.get_combinations(self.game.player_produce[p],self.game.player_cash[self.game.active_player]):
                        #if len(x[1]) > free_space: continue
                        next_game = copy.deepcopy(self.game)
                        next_game.buy_produce(p, x[1])
                        next_game.make_move(MOVE = BUYPRODUCE)
                        node = self.create_child(next_game,(BUYPRODUCE,p,x[1]))
                        self.children_nodes.append(node)

            if PRODUCE in moves:
                next_game = copy.deepcopy(self.game)
                next_game.run_factory()
                next_game.make_move(MOVE = PRODUCE)
                node = self.create_child(next_game,PRODUCE)
                self.children_nodes.append(node)

            # PASS
            if PASS in moves:
                next_game = copy.deepcopy(self.game)
                next_game.make_move(MOVE = PASS)
                node = self.create_child(next_game,PASS)
                self.children_nodes.append(node)

    # returns child with highest ucb
    def best_child(self,playerID,ucb=True,verbose=False):
        best_ucb = -1
        best_node = self.children_nodes[0]
        for child in self.children_nodes:
            score = child.ucb_score if ucb else child.get_score(playerID)
            if (verbose): 
                child.ucb(playerID, verbose=True)
                print(f"MCTS Child {child.move}: Score {score} Num Sims {child.num_sims} AMAF {child.amaf_num_sims}")
            if score > best_ucb:
                best_ucb = score
                best_node = child
        return best_node

    # returns flat score without amaf/explore
    def get_score(self,playerID):
        return self.utility[playerID]/self.num_sims if self.num_sims > 0 else -1

    def ucb(self,playerID, verbose=False):
        if self.num_sims == 0 or self.parent == -1 or self.parent.num_sims == 0: return math.inf
        if (self.RAVE):
            if self.amaf_num_sims == 0: return math.inf
            RAVE = self.amaf_num_sims/(self.num_sims+self.amaf_num_sims+4*(self.b**2)*self.num_sims*self.amaf_num_sims)
            if (verbose): print(f"RAVE {RAVE} UCB {self.utility[playerID]/self.num_sims} RAVE {self.amaf_utility[playerID]/self.amaf_num_sims} EXPLORE {(self.LAMBDA*math.log(self.parent.num_sims)/self.num_sims)**0.5}")
            return (1-RAVE)*(self.utility[playerID]/self.num_sims)+RAVE*(self.amaf_utility[playerID]/self.amaf_num_sims)+(self.LAMBDA*math.log(self.parent.num_sims)/self.num_sims)**0.5
        else:
            if (verbose): print(f"UCB {self.utility[playerID]/self.num_sims} EXPLORE {(self.LAMBDA*math.log(self.parent.num_sims)/self.num_sims)**0.5}")
            return (self.utility[playerID]/self.num_sims)+(self.LAMBDA*math.log(self.parent.num_sims)/self.num_sims)**0.5

    def rollout(self, NUM_ROLLOUT = 100):
        out = [0 for x in range(self.game.NUM_PLAYERS)]
        # replace at least self with random
        temp_game = copy.deepcopy(self.game)

        for x in range(NUM_ROLLOUT):
            next_game = copy.deepcopy(temp_game)
            while not next_game.game_over:
                next_game.make_move()
            for p in range(temp_game.NUM_PLAYERS):
                # maximise score/count 1st place
                out[p] += next_game.final_score[p]
        return out

    # score is from rollout()
    # playerID is from whose pov are we calculating ucb
    # Note: ucb is calculated for the node whenever there is a change
    def backpropagate(self, score, playerID, NUM_ROLLOUT = 100):
        data = np.array(score)
        node = self
        while node != -1:
            if hasattr(node, 'utility'): node.utility = np.add(node.utility,data)
            else: node.utility = data
            node.num_sims += NUM_ROLLOUT
            node.ucb_score = node.ucb(playerID)

            if (self.RAVE and node.parent != -1):
                search_type = self.move[0] if type(self.move) != int else self.move
                for n in node.parent.children_nodes: # siblings
                    node_type = n.move[0] if type(n.move) != int else n.move
                    if (search_type == node_type):
                        if hasattr(n, 'amaf_utility'): n.amaf_utility = np.add(n.amaf_utility,data)
                        else: n.amaf_utility = data
                        n.amaf_num_sims += NUM_ROLLOUT
                    n.ucb_score = n.ucb(playerID)
            node = node.parent

class ISMCTSNode(MCTSNode):
    def __init__(self,game,parent,move,infosets,ROLLOUT_SHORTCUT=False):
        super().__init__(game,parent,move)

        #INFOSET
        self.INFOSETS = infosets
        self.ROLLOUT_SHORTCUT = ROLLOUT_SHORTCUT # whether to use rollout shortcut (should only be true for randomAgents)

    # wrapper for creating new node
    def create_child(self, game, move):
        return ISMCTSNode(game,self,move,self.INFOSETS,ROLLOUT_SHORTCUT=self.ROLLOUT_SHORTCUT)

    def ucb(self,playerID,verbose=False):
        if self.num_sims == 0 or self.parent == -1 or self.parent.num_sims == 0: return math.inf

        # assume each info set equally likely
        avg_utility = np.mean(self.utility, axis=0)[playerID]

        if (self.RAVE):
            if self.amaf_num_sims == 0: return math.inf
            avg_amaf_utility = np.mean(self.amaf_utility, axis=0)[playerID]
            RAVE = self.amaf_num_sims/(self.num_sims+self.amaf_num_sims+4*(self.b**2)*self.num_sims*self.amaf_num_sims)
            if (verbose): print(f"RAVE {RAVE} UCB {avg_utility/self.num_sims} RAVE {avg_amaf_utility/self.amaf_num_sims} EXPLORE {(self.LAMBDA*math.log(self.parent.num_sims)/self.num_sims)**0.5}")
            return (1-RAVE)*(avg_utility/self.num_sims)+RAVE*(avg_amaf_utility/self.amaf_num_sims)+(self.LAMBDA*math.log(self.parent.num_sims)/self.num_sims)**0.5
        else:
            if (verbose): print(f"UCB {avg_utility/self.num_sims} EXPLORE {(self.LAMBDA*math.log(self.parent.num_sims)/self.num_sims)**0.5}")
            return (avg_utility/self.num_sims)+(self.LAMBDA*math.log(self.parent.num_sims)/self.num_sims)**0.5

    # returns flat score without amaf/explore
    def get_score(self,playerID):
        return np.mean(self.utility, axis=0)[playerID]/self.num_sims if self.num_sims > 0 else -1

    # split into possible info sets, assume equally likely
    def rollout(self, NUM_ROLLOUT = 100):
        if(self.ROLLOUT_SHORTCUT):
            # SHORTCUT (CAN ONLY SIMULATE AGENTS THAT DO NOT ACCESS THE SCORE AT ALL, INCLUDING THEIR OWN SCORECARD), 
            # JUST SWAP THE SCORE CARDS AT THE END
            out = [[0 for _ in range(self.game.NUM_PLAYERS)] for _ in self.INFOSETS] # score for each infoset
            for x in range(NUM_ROLLOUT):
                next_game = copy.deepcopy(self.game)
                while not next_game.game_over:
                    next_game.make_move()
                
                # when game ends score for each info set
                for i,SCORECARDS in enumerate(self.INFOSETS): 
                    next_game.player_cards = SCORECARDS
                    final_score = next_game.final_scoring() # recalc score
                    for p in range(self.game.NUM_PLAYERS):
                        out[i][p] += final_score[p]
            return out

        # THE NORMAL WAY (NON RANDOM AGENTS), SIMULATED AGENTS CAN ACCESS SCORECARD INFO TO DECIDE MOVES
        out = []
        for SCORECARDS in self.INFOSETS:
            TEMP = [0 for x in range(self.game.NUM_PLAYERS)] # score for this infoset
            INFO_game = copy.deepcopy(self.game)
            INFO_game.player_cards = SCORECARDS

            # number of rollouts have to be divided to each infoset
            for x in range(round(max(NUM_ROLLOUT/len(self.INFOSETS),1))):
                next_game = copy.deepcopy(INFO_game)
                while not next_game.game_over:
                    next_game.make_move()
                for p in range(self.game.NUM_PLAYERS):
                    TEMP[p] += next_game.final_score[p]
            out.append(TEMP)
        return out

class MCTSAgent(RandomAgent):
    def __init__(self,game,id):
        super().__init__(game,id)
        self.name = "MCTSAgent"
        self.verbose = False

        if game.INFO_MODE == SEMI_PERFECT:
            self.infosets = self.find_infosets()
            if self.verbose: 
                print(f"Infosets")
                for x in self.infosets: print(x)
    
    def find_infosets(self):
        cards = self.game.generate_card(GET_COMBI=True)
        cards.remove(self.game.player_cards[self.playerID]) # cant be my own card
        if self.verbose: print("Infosets: ",cards)
        perms = permutations(cards, self.game.NUM_PLAYERS-1)
        out = []
        for i in list(perms):
            infoset = list(i)
            infoset.insert(self.playerID,self.game.player_cards[self.playerID]) # add my known score card
            out.append(infoset)
        return out

    # Random Agent selects all from all moves moves types playable
    # and selects each with an equal probability
    # only if no moves are playable does the agent pass
    # bidding policy is 50% accept and decline if able
    # pricing policy is to randomly allocate between avaliable prices
    def make_move(self, MOVE = -1):
        if MOVE in [BUYPRODUCE,BUYWARES,-1]:
            move = self.search(MOVE = MOVE)
            choice = move[0] if type(move) != int else move
        else:
            choice = MOVE

        if AUCTION == choice:
            self.game.start_auction()
            return AUCTION

        elif BUYWARES == choice:
            self.game.buy_wares(move[1], move[2])
            return BUYWARES

        elif BUYPRODUCE == choice:
            self.game.buy_produce(move[1], move[2])
            return BUYPRODUCE

        # Produce
        elif PRODUCE == choice:
            self.game.run_factory()
            return PRODUCE

        elif PASS == choice:
            if (self.game.verbose): print(">>> Player {} Passed turn <<<".format(self.playerID))
            return PASS

        else:
            raise Exception(f"Error unknown move by MCTS Agent, {choice}")
            return False

    def accept_bid(self,bid,product,buyer,bids):
        if (bid > self.game.player_cash[self.playerID]): # NO CHOICE
            return True
        else:
            NUM_ROLLOUTS = NUM_ROLLOUT_PER_ITER*ROLLOUT_BID_MOD
            # just rollout accept/pass (!! in theory could run a full mcts tree)
            accept_root = self.createRoot(self.game)
            accept_root.game.resolve_auction(self.playerID, buyer, product, bids)
            accept_root.game.make_move(MOVE = AUCTION)
            data = accept_root.rollout(NUM_ROLLOUTS)
            accept_root.backpropagate(data,self.playerID,NUM_ROLLOUTS)
            accept_score = accept_root.get_score(self.playerID)

            reject_root = self.createRoot(self.game)
            reject_root.game.resolve_auction(self.playerID, self.playerID, product, bids)
            reject_root.game.make_move(MOVE = AUCTION)
            data = reject_root.rollout(NUM_ROLLOUTS)
            reject_root.backpropagate(data,self.playerID,NUM_ROLLOUTS)
            reject_score = reject_root.get_score(self.playerID)

            if self.verbose: 
                print("[Accept_bid score] ", accept_score)
                print("[Reject_bid score] ", reject_score)
            return True if accept_score >= reject_score else False

    def create_bid_root(self,product):
        max_bid = min(self.game.player_cash[self.playerID],sum(product)*10) # dont spend more than 10/c
        if max_bid == 0: return 0
        bids = np.full(self.game.NUM_PLAYERS,-1)
        root = self.createRoot(self.game)
        for bid in range(0,max_bid+1,1 if sum(product)<3 else 2): # manually create children
            bids[self.playerID] = bid
            next_game = copy.deepcopy(root.game)
            next_game.start_auction(starting_bids=bids) # start auction where I bid X
            next_game.make_move(MOVE = AUCTION)
            root.children_nodes.append(root.create_child(next_game,bid))
        return root

    def get_bid(self, product):
        root = self.create_bid_root(product)
        if root == 0: return 0 # cash = 0
        return self.mcts_get_bid(product, root)

    def mcts_get_bid(self, product, root):
        NUM_ROLLOUTS = NUM_ROLLOUT_PER_ITER
        for _ in range(NUM_ITER):
            # selection
            window = root
            while len(window.children_nodes) != 0 and not window.game.game_over:
                window = window.best_child(self.playerID)

            # No expansion here?

            # rollout
            data = window.rollout(NUM_ROLLOUTS)

            # backprop
            window.backpropagate(data,self.playerID,NUM_ROLLOUTS)

        if self.verbose: print(f"[Get Bid] Num Sims = {NUM_ROLLOUTS}")
        return root.best_child(self.playerID,ucb=False,verbose=self.verbose).move

    # pricing policies
    # called by game() after buy action
    def factory_reprice(self):
        self.shufflePrices(self.game.player_produce[self.playerID],self.game.get_numFacts(),self.game.MIN_PROD_P,self.game.MAX_PROD_P,WH=False)

    def warehouse_reprice(self,player,cart):
        self.shufflePrices(self.game.player_wares[self.playerID],self.game.player_warehouses[self.playerID],self.game.MIN_WARE_P,self.game.MAX_WARE_P,WH=[player,cart])
    
    # goods is the player WH/Produce
    #self.player_produce[player][colour] = [priced at 1, price at 3 etc]
    def shufflePrices(self, goods, cap, MIN, MAX, WH=False):
        root = self.createRoot(self.game)

        if self.verbose: print("Starting Containers",goods)
        colours = [len(goods[x]) for x in range(self.game.NUM_CONTAINERS)] # number of each colour currently in store
        num_drop = sum(colours) - cap*2 # number of containers to drop
        if num_drop >= 1:
            prices = list(range(MIN,MAX-1)) #reduce search space if many containers
        else:
            prices = list(range(MIN,MAX))
        if num_drop > 0:
            temp = []
            for x in range(self.game.NUM_CONTAINERS): 
                if colours[x] > 0: temp.append(x)
            possible_drops = list(combinations_with_replacement(temp,num_drop))
        else: possible_drops = [[]]
        for drop in possible_drops: # what containers to keep
            choose = copy.copy(colours) # num colour kept
            flag = False
            for x in drop: 
                choose[x] -= 1
                if choose[x] < 0: 
                    flag = True
                    break #better way might be => could have possbile_drops only of valid
            if flag: continue

            # do price perms for each colour
            if self.verbose: 
                print("Dropping:",drop)
                print("Chosen:",choose)
            # combination explosion 5^4 = 625
            #l = [list(combinations_with_replacement(prices,choose[x])) for x in range(self.game.NUM_CONTAINERS)]
            #print(l)
            # (abstraction) assume all colours sold at same price + price range only 1-3
            l = [[[i]*choose[x] if choose[x]>1 else [i] for i in prices] if choose[x]>0 else [()] for x in range(self.game.NUM_CONTAINERS)]
            #print(l)
            combi = [p for p in product(*l)] #combination for each colour
            #print(combi)

            for item in combi: #((1,2),2,3) => C1 priced at 1,2. C2 priced at 2
                new = [[] for x in range(self.game.NUM_CONTAINERS)]
                for c in range(self.game.NUM_CONTAINERS):
                    # convert to price, if 1 = P, else = (P,P,..)
                    if choose[c] == 1: new[c].append(item[c][0])
                    else:
                        for i in range(choose[c]):
                            new[c].append(item[c][i])

                # create child
                #print(new)
                # check if last move was made
                next_game = copy.deepcopy(root.game)
                if WH: #buy produce (the containers would already be taken, since reprice last)
                    next_game.make_move(MOVE = PRODUCE)
                    next_game.player_wares[self.playerID] = new
                else: #produce
                    next_game.make_move(MOVE = BUYPRODUCE)
                    next_game.player_produce[self.playerID] = new
                root.children_nodes.append(root.create_child(next_game,(drop,new))) # [0] is type for RAVE

        NUM_ROLLOUTS = NUM_ROLLOUT_PER_ITER
        for _ in range(NUM_ITER):
            # selection
            window = root
            while len(window.children_nodes) != 0 and not window.game.game_over:
                window = window.best_child(self.playerID)

            # No expansion here (just monte carlo)

            # rollout
            data = window.rollout(NUM_ROLLOUTS)

            # backprop
            window.backpropagate(data,self.playerID,NUM_ROLLOUTS)

        new = root.best_child(self.playerID,ucb=False,verbose=self.verbose).move[1]
        if WH: #buy produce (the containers would already be taken, since reprice last)
            self.game.player_wares[self.playerID] = new
            if self.verbose: print(f"[Get Price] WH = {new}")
        else: #produce
            self.game.player_produce[self.playerID] = new
            if self.verbose: print(f"[Get Price] Fact = {new}")
    
    # MCTS Functions
    # if MOVE != -1, only search that action (only allow BUYPRODUCE,BUYWARES,-1)
    def search(self, MOVE = -1):
        root = self.createRoot(self.game)
        root.make_children(MOVE=MOVE)

        NUM_ROLLOUTS = NUM_ROLLOUT_PER_ITER
        for _ in range(NUM_ITER):
            # selection
            window = root
            while len(window.children_nodes) != 0 and not window.game.game_over:
                window = window.best_child(self.playerID)
            
            # expand (if no expand, just monte carlo sampling)
            '''
            if not window.game.game_over:
                window.make_children(MOVE=MOVE)
            '''

            # rollout
            data = window.rollout(NUM_ROLLOUTS)

            # backprop
            window.backpropagate(data,self.playerID,NUM_ROLLOUTS)
            
        if (self.verbose): print(f"[MCTS] Num Sims = {root.num_sims}")

        return root.best_child(self.playerID,ucb=False,verbose=self.verbose).move
    
    def createRoot(self, base_game):
        modified_game = copy.deepcopy(base_game)
        modified_game.verbose = False
        modified_game.anticheat = False
        modified_game.logfile = ""
        for x in range(modified_game.NUM_PLAYERS):
            modified_game.players[x] = RandomAgent(modified_game,x)

        if self.game.INFO_MODE == PERFECT: return MCTSNode(modified_game,-1,-1)
        elif self.game.INFO_MODE == SEMI_PERFECT: return ISMCTSNode(modified_game,-1,-1,self.infosets,ROLLOUT_SHORTCUT=True)
        
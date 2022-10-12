import numpy as np
import random #import random, shuffle, randint, choice
from itertools import combinations
import time
import copy
from numpy.random import choice

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

# NODE PRICING (ALSO CHANGE IN CFRTRAINER)
NODE_PRICES = [[3,3,3],[0,0,0],[0,1,2],[1,2,3]] #blueprints
#NUM_REPRICES = 4 # 3 COLOURS, 3 PRICES
#NODE_PRICES = [[]] + list(np.ndindex(NUM_REPRICES, NUM_REPRICES, NUM_REPRICES)) 

# BUCKET ABSTRACTIONS
CASH_BUCKET = [0]*5+[1]*5+[2]*5+[3]*10 # EXPANDEDMCCFR
#CASH_BUCKET = [0]*5+[1]*15 # BASEMCCFR
PRODUCE_BUCKET = np.array([-1,0,1,2,3,-2,-2]) # PRICING BUCKET
WARES_BUCKET = np.array([-1,-1,0,1,2,3,-2,-2])

class CFRNode:
    __slots__ = ["infoset","n_actions","regret_sum","strategy_sum","strategy","explored"]
    def __init__(self, infoset, n_actions):
        self.infoset = infoset
        self.n_actions = n_actions
        self.explored = 0 # number of times node was explored

        self.regret_sum = np.zeros(self.n_actions)
        self.strategy_sum = np.zeros(self.n_actions)
        self.strategy = np.repeat(1 / self.n_actions, self.n_actions)
        #self.average_strategy = np.repeat(1 / self.n_actions, self.n_actions)

    def clear_strategy(self):
        self.strategy_sum = np.zeros(self.n_actions)
        self.explored = 0

    # this is strategy taking into account current regret
    def get_strategy(self):
        self.regret_sum[self.regret_sum < 0] = 0 # regrets floored at zero in cfr+
        normalizing_sum = sum(self.regret_sum)
        self.strategy = self.regret_sum
        if normalizing_sum > 0:
            self.strategy = self.strategy / normalizing_sum
        else:
            self.strategy = np.repeat(1 / self.n_actions, self.n_actions)
        return self.strategy

    def get_action(self, strategy, valid = False):
        strategy = copy.copy(strategy)
        if valid: 
            # find invalid actions and set them to 0
            np.put(strategy,np.setdiff1d(np.arange(self.n_actions), valid),0)
            if not np.any(strategy): # valid actions are all 0
                if valid == [PASS]: return PASS
                try: valid.remove(PASS)
                except Exception: pass
                np.put(strategy,valid,1)
            strategy /= strategy.sum() # normalise aft removing invalid actions
        return choice(np.arange(self.n_actions), p=strategy)

    # this is strategy equilibrium (final strat to play)
    def get_average_strategy(self):
        strategy = self.strategy_sum

        normalizing_sum = np.sum(strategy)
        if normalizing_sum > 0:
            strategy = strategy / normalizing_sum
        else:
            strategy = np.repeat(1 / self.n_actions, self.n_actions)
        return strategy

    def __str__(self):
        """ avg_strategies = ['{:03.2f}'.format(x)
                      for x in self.get_average_strategy()] """
        strategies = ['{:03.2f}'.format(x)
                      for x in self.get_strategy()]
        regret_sum = ['{:03.2f}'.format(x)
                      for x in self.regret_sum]
        return '{} {} {} Exp {}'.format(self.infoset.ljust(6), regret_sum, strategies, self.explored)


# gets index of what to buy
# game_colour[infoset colour] -> corresponding colour in game
# NOTE: THE COLOURS ARE REF FROM SCORE CARD NOT GAME COLOURS
def get_actions_buy_infoset(infoset,game_colour=-1):
    shop = infoset.split("|")[-1].split("-")

    options = [] # potential buys
    for colour,x in enumerate(shop):
        if x == "": continue
        for price in x.split(","):
            if game_colour == -1: options.append(str(colour)+price) # colour + price 
            else: options.append(str(game_colour[colour])+price)
    #print(options)

    # generate combinations from options
    carts = list()
    #limit = min(infoset.split("/")[1][0],len(options)) # dont buy more than storage can hold
    for n in range(1,len(options) + 1):
        carts += list(combinations(options, n))

    # convert to buy format
    possible = []
    for x in carts:
        cart = np.zeros(3, dtype = int)
        for item in x:
            colour = int(item[0])
            cart[colour] += 1
        cart = auction_to_cart(cart)
        if not cart in possible: possible.append(cart)
    #print(possible)
    return [sorted(x) for x in possible]

# given a gamestate and output of get_actions_buy_infoset()
# return indexes of valid actions
def get_valid_buy(gamestate, infoset, goods):
    order = get_score_colour_order(gamestate)
    #print("Order ", order)

    possible = get_actions_buy_infoset(infoset,order)
    valid = gamestate.get_combinations(goods, gamestate.player_cash[gamestate.active_player])
    valid = [sorted(x[1]) for x in valid]
    #print("Possible ", possible)
    #print("Valid ", valid)

    indexes = []
    for index,value in enumerate(possible):
        if value in valid: indexes.append(index)

    #print(indexes)
    return indexes

# return list of colours in scorecard order for active player
def get_score_colour_order(gamestate):
    order = [(x,gamestate.player_cards[gamestate.active_player][x]) for x in range(gamestate.NUM_CONTAINERS)]
    order.sort(key=lambda x: x[1])
    order = [x[0] for x in order]
    return order

# converts auction from game to cart from game
def auction_to_cart(input):
    out = []
    for i in range(len(input)):
        if input[i] != 0: out.append((i,input[i]))
    return out

# HOW MUCH IS CONTIANERS ACTUALLY WORTH TO PLAYER
# product = [x for each colour]
# score_card = [[player 0 container values],...]
def containers_score(product, score_card):
    return sum(np.multiply(np.array(product), np.array(score_card)))

# ABSTRACTION FUNCTIONS
# used for baseMCCFR
def abstract_game(gamestate, ref_player):
    s = ""

    # CASH BUCKET
    if gamestate.player_cash[ref_player] < len(CASH_BUCKET):
        s += str(CASH_BUCKET[gamestate.player_cash[ref_player]]) + "/"
    else:
        s += "m/"

    # CONTAINER ORDED BY SCORE CARD
    order = [(x,gamestate.player_cards[ref_player][x]) for x in range(gamestate.NUM_CONTAINERS)]
    order.sort(key=lambda x: x[1]) # asc order of colour value

    # SUM OF REF P/W/C
    p = 0
    w = 0
    c = max(sum(gamestate.player_cargo[ref_player]),4)
    for (colour,_) in order:
        # for self colour and price matters
        #p += ",".join(self.PRODUCE_BUCKET[gamestate.player_produce[ref_player][colour]])+"-"
        #w += ",".join(self.WARES_BUCKET[gamestate.player_wares[ref_player][colour]])+"-"
        # for self only colours matter not price (hence sum)
        """ p += str(len(gamestate.player_produce[ref_player][colour]))+"-"
        w += str(len(gamestate.player_wares[ref_player][colour]))+"-"
        c += str(gamestate.player_cargo[ref_player][colour])+"-" """
        # just sum ignore colour
        p += len(gamestate.player_produce[ref_player][colour])
        w += len(gamestate.player_wares[ref_player][colour])
    s += str(p)+"/"+str(w)+"/"+str(c)+"|"

    # Other players
    merged_product = 9 # price bucket
    merged_wares = 9
    #merged_cargo = np.zeros(gamestate.NUM_CONTAINERS)
    merged_cargo = 0 #sum
    opponents = []
    for x in range(1,gamestate.NUM_PLAYERS):
        temp = ""
        player = (ref_player+x)%gamestate.NUM_PLAYERS

        # CASH
        if gamestate.player_cash[player] < len(CASH_BUCKET):
            temp += str(CASH_BUCKET[gamestate.player_cash[player]])
        else:
            temp += "m"
        opponents.append(temp)

        # CARGO
        merged_cargo += max(sum(gamestate.player_cargo[player]),4) # sum capped at 4
        #merged_cargo += gamestate.player_cargo[player] # sum of colours

        for (colour,_) in order: 
            # only min price for each colour
            """ if gamestate.player_produce[player][colour]:
                merged_product[colour] = min(merged_product[colour],min(PRODUCE_BUCKET[gamestate.player_produce[player][colour]]))
            if gamestate.player_wares[player][colour]:
                merged_wares[colour] = min(merged_wares[colour],min(WARES_BUCKET[gamestate.player_wares[player][colour]])) """

            # only min price
            if gamestate.player_produce[player][colour]:
                merged_product = min(merged_product,min(PRODUCE_BUCKET[gamestate.player_produce[player][colour]]))
            if gamestate.player_wares[player][colour]:
                merged_wares = min(merged_wares,min(WARES_BUCKET[gamestate.player_wares[player][colour]]))

    opponents.sort() # order irrelevant
    #s += "|".join(opponents) + "|" + "|".join(np.array(merged_cargo, dtype=str)) + "|"
    s += "|".join(opponents) + "|" + str(merged_cargo)+"|"

    # What is on sale (merged)
    """ p = "-".join(np.array(merged_product).astype(str))
    w = "-".join(np.array(merged_wares).astype(str))
    s += p+"/"+w """
    s += str(merged_product) + "/" + str(merged_wares)

    return s

# used for ExpandedMCCFR
# colour split of own cargo and others cargo
# min price for each colour
def expand_abstract_game(gamestate, ref_player):
    s = ""

    # CASH BUCKET
    if gamestate.player_cash[ref_player] < len(CASH_BUCKET):
        s += str(CASH_BUCKET[gamestate.player_cash[ref_player]]) + "/"
    else:
        s += "m/"

    # CONTAINER ORDED BY SCORE CARD
    order = [(x,gamestate.player_cards[ref_player][x]) for x in range(gamestate.NUM_CONTAINERS)]
    order.sort(key=lambda x: x[1]) # asc order of colour value

    # SUM OF REF P/W/C
    p = 0
    w = 0
    #c = max(sum(gamestate.player_cargo[ref_player]),4)
    c = ""
    for (colour,_) in order:
        # for self colour and price matters
        #p += ",".join(self.PRODUCE_BUCKET[gamestate.player_produce[ref_player][colour]])+"-"
        #w += ",".join(self.WARES_BUCKET[gamestate.player_wares[ref_player][colour]])+"-"
        # for self only colours matter not price (hence sum)
        """ p += str(len(gamestate.player_produce[ref_player][colour]))+"-"
        w += str(len(gamestate.player_wares[ref_player][colour]))+"-"
        c += str(gamestate.player_cargo[ref_player][colour])+"-" """
        # just sum ignore colour
        p += len(gamestate.player_produce[ref_player][colour])
        w += len(gamestate.player_wares[ref_player][colour])
        c += str(gamestate.player_cargo[ref_player][colour])+"-"
    s += str(p)+"/"+str(w)+"/"+c[:-1]+"|"

    # Other players
    #merged_product = 9 # price bucket
    #merged_wares = 9
    merged_product = np.zeros(gamestate.NUM_CONTAINERS)
    merged_wares = np.zeros(gamestate.NUM_CONTAINERS)
    merged_cargo = np.zeros(gamestate.NUM_CONTAINERS)
    #merged_cargo = 0 #sum
    opponents = []
    for x in range(1,gamestate.NUM_PLAYERS):
        temp = ""
        player = (ref_player+x)%gamestate.NUM_PLAYERS

        # CASH
        if gamestate.player_cash[player] < len(CASH_BUCKET):
            temp += str(CASH_BUCKET[gamestate.player_cash[player]])
        else:
            temp += "m"
        opponents.append(temp)

        # CARGO
        #merged_cargo += max(sum(gamestate.player_cargo[player]),4) # sum capped at 4
        merged_cargo += gamestate.player_cargo[player] # sum of colours

        for (colour,_) in order: 
            # only min price for each colour
            if gamestate.player_produce[player][colour]:
                merged_product[colour] = min(merged_product[colour],min(PRODUCE_BUCKET[gamestate.player_produce[player][colour]]))
            if gamestate.player_wares[player][colour]:
                merged_wares[colour] = min(merged_wares[colour],min(WARES_BUCKET[gamestate.player_wares[player][colour]]))

            # only min price
            """ if gamestate.player_produce[player][colour]:
                merged_product = min(merged_product,min(PRODUCE_BUCKET[gamestate.player_produce[player][colour]]))
            if gamestate.player_wares[player][colour]:
                merged_wares = min(merged_wares,min(WARES_BUCKET[gamestate.player_wares[player][colour]])) """

    opponents.sort() # order irrelevant
    s += "|".join(opponents) + "|" + "|".join(np.array(merged_cargo, dtype=str)) + "|"
    #s += "|".join(opponents) + "|" + str(merged_cargo)+"|"

    # What is on sale (merged)
    """ p = "-".join(np.array(merged_product).astype(str))
    w = "-".join(np.array(merged_wares).astype(str))
    s += p+"/"+w """
    s += str(merged_product) + "/" + str(merged_wares)

    return s

# used for baseMCCFR
def abstract_auction(gamestate, ref_player):
    host = gamestate.active_player
    upper = containers_score(gamestate.player_cargo[host], gamestate.player_cards[ref_player])

    s = ""

    # CASH
    s += str(abstract_auction_cash(upper,gamestate.player_cash[ref_player])) + "/"

    order = [(x,gamestate.player_cards[ref_player][x]) for x in range(gamestate.NUM_CONTAINERS)]
    order.sort(key=lambda x: x[1]) # asc order of colour value

    #pw = 0
    c = max(sum(gamestate.player_cargo[ref_player]),4) # CARGO
    cart = []
    for (colour,_) in order:
        #pw += len(gamestate.player_produce[ref_player][colour])
        #pw += len(gamestate.player_wares[ref_player][colour])
        cart.append(str(gamestate.player_cargo[host][colour])) # AUCTION CART
    #s += str(pw)+"/"+str(c)+"|"
    s += str(c)+"|"

    # Other players (cash and cargo)
    merged_cargo = 0
    opponents = []
    for x in range(1,gamestate.NUM_PLAYERS):
        temp = ""
        player = (ref_player+x)%gamestate.NUM_PLAYERS
        if player == host: continue # ignore host player

        temp += str(abstract_auction_cash(upper,gamestate.player_cash[player]))
        opponents.append(temp)

        merged_cargo += max(sum(gamestate.player_cargo[player]),4) # capped at 4

    opponents.sort() # order irrelevant
    s += "|".join(opponents) + "|" + str(merged_cargo) + "|" 

    # host 
    s += str(abstract_auction_cash(upper,gamestate.player_cash[host])) + "/" + "-".join(cart)

    return s, upper

# used for ExpandedMCCFR
# colour sum for awaiting auction
def expand_abstract_auction(gamestate, ref_player):
    host = gamestate.active_player
    upper = containers_score(gamestate.player_cargo[host], gamestate.player_cards[ref_player])

    s = ""

    # CASH
    s += str(abstract_auction_cash(upper,gamestate.player_cash[ref_player])) + "/"

    order = [(x,gamestate.player_cards[ref_player][x]) for x in range(gamestate.NUM_CONTAINERS)]
    order.sort(key=lambda x: x[1]) # asc order of colour value

    #pw = 0
    c = max(sum(gamestate.player_cargo[ref_player]),4) # CARGO
    cart = []
    for (colour,_) in order:
        #pw += len(gamestate.player_produce[ref_player][colour])
        #pw += len(gamestate.player_wares[ref_player][colour])
        cart.append(str(gamestate.player_cargo[host][colour])) # AUCTION CART
    #s += str(pw)+"/"+str(c)+"|"
    s += str(c)+"|"

    # Other players (cash and cargo)
    merged_cargo = np.zeros(gamestate.NUM_CONTAINERS)
    #merged_cargo = 0
    opponents = []
    for x in range(1,gamestate.NUM_PLAYERS):
        temp = ""
        player = (ref_player+x)%gamestate.NUM_PLAYERS
        if player == host: continue # ignore host player

        temp += str(abstract_auction_cash(upper,gamestate.player_cash[player]))
        opponents.append(temp)

        #merged_cargo += max(sum(gamestate.player_cargo[player]),4) # capped at 4
        merged_cargo += gamestate.player_cargo[player] # sum of colours

    opponents.sort() # order irrelevant
    
    s += "|".join(opponents) + "|" + "|".join(np.array(merged_cargo, dtype=str)) + "|"
    #s += "|".join(opponents) + "|" + str(merged_cargo) + "|" 

    # host 
    s += str(abstract_auction_cash(upper,gamestate.player_cash[host])) + "/" + "-".join(cart)

    return s, upper

def abstract_buy(gamestate, ref_player, seller, WH=False):
    s = "W|" if WH else "F|"

    # Perspective player
    if gamestate.player_cash[ref_player] < len(CASH_BUCKET):
        s += str(CASH_BUCKET[gamestate.player_cash[ref_player]]) + "/"
    else:
        s += "m/"

    order = [(x,gamestate.player_cards[ref_player][x]) for x in range(gamestate.NUM_CONTAINERS)]
    order.sort(key=lambda x: x[1]) # asc order of colour value

    if WH: # buywares
        s += str(sum(gamestate.player_cargo[ref_player])) + "|"
        store = gamestate.player_wares[seller]
        temp = ""
        for (colour,_) in order:
            temp += ",".join(np.array(store[colour]).astype(str))+"-"
        s += temp[:-1]
    else: # buyproduce
        w = 0
        store = gamestate.player_produce[seller]
        temp = ""
        for (colour,_) in order:
            w += len(gamestate.player_wares[ref_player][colour])
            temp += ",".join(np.array(store[colour]).astype(str))+"-"
        s += str(w) + "|" + temp[:-1]
    #print(f"{s} Buy wares {WH} seller {seller}")
    return s

# abstraction for cash buckets in auction
def abstract_auction_cash(upper,x):
    if upper <= 10:
        return min(x//3,4)
    else:
        return min(x//(upper//3),4)

# given an auction bid bucket return an array of bids corresponding
def unabstract_auction_cash(cash,upper,x):
    if upper <= 10:
        num = 3
    else:
        num = upper//3

    lower = num*x
    if cash < lower: # cant afford
        return [0]

    if x >= 4: # above upper limit
        if cash < lower+num*2-1:
            num = cash - lower+1
        else:
            num *= 2

    elif cash < lower+num-1:
        num = cash - lower +1
            
    return np.linspace(lower, lower+num-1, num=num, dtype = int).tolist()

# DIY regex matcher
# colours are sorted by least to most valuable on scorecard
def get_price_index(match):
    check = np.array(match, dtype=int)
    check = check[check != -1]
    indexes = [] # indexes where tuples match
    for i,v in enumerate(NODE_PRICES):
        flag = True
        for j in check:
            if match[j] != v[j]: 
                flag = False
                break
        if flag: 
            #print("Match ",v)
            indexes.append(i)
    return indexes

# get pricing strategy from index
def getPricingStrategy(index, order):
    if NODE_PRICES[index] == []: # random
        return [random.randint(0, len(PRODUCE_PRICES)-1) for x in order]
    else:
        return [NODE_PRICES[index][x] for x in order] # reorder for game

# given a set of containers (WH/FACT) return a priced version 
# price is a list of prices for each colour
def set_pricing(store, pricing, TYPE, num_drops = 0):
    # DROP LOWEST TO HIGHEST PRICE
    if num_drops > 0:
        order = [(x,pricing[x]) for x in range(len(store))]
        order.sort(key=lambda x: x[1])
        for c,_ in order:
            if len(store[c]) > 0: 
                if len(store[c]) >= num_drops:
                    num_drops -= len(store[c])
                    store[c] = []
                else:
                    store[c] = store[c][num_drops:]
                    break

    for c in range(len(store)):
        # convert pricing bucket -> price
        if TYPE == PRODUCE: price = PRODUCE_PRICES[pricing[c]]
        else: price = WARES_PRICES[pricing[c]]
        store[c] = [price]*(len(store[c])) # assume same 
    return store

def display_results(i_map,number = 50):
    print()
    print('Strategies:')
    sorted_items = sorted(i_map.items(), key=lambda x: x[0])
    count = 0
    for v in sorted_items:
        print(v[1])
        count += 1
        if count > number:
            break
    print()
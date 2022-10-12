import random
from agent import Agent

PRODUCE = 0
BUYPRODUCE = 1
BUYWARES = 2
AUCTION = 3
PASS = 4
SAILSEA = 5
BUYFACT = 6
BUYWAREHOUSE = 7

class RandomAgent(Agent):
    def __init__(self,game,id):
        super().__init__(game,id)
        self.name = "Random2Agent"

    # Random Agent selects all from all possible moves types playable
    # and selects each with an equal probability
    # only if no moves are playable does the agent pass
    # bidding policy is 50% accept and decline if able
    # pricing policy is to randomly allocate between avaliable prices
    def make_move(self, MOVE = -1): 
        actions = self.game.get_moves()

        while True:
            if MOVE in actions:
                action = MOVE
            else:
                action = random.choice(actions)

            if action == PASS:
                if (self.game.verbose): print(">>> Player {} Passed turn <<<".format(self.playerID))
                return PASS

            # Run factory, set prices
            if action == PRODUCE:
                if (self.game.get_numProduce() >= self.game.get_numFacts()*2): # dont produce is full
                    actions.remove(action)
                    continue
                self.game.run_factory()
                return PRODUCE

            # Buy from factories, set prices
            elif action == BUYPRODUCE:
                if (self.game.get_numWares() >= self.game.player_warehouses[self.playerID]*2): # dont produce is full
                    actions.remove(action)
                    continue

                # choose player
                PLAYER = random.choice(self.game.who_buyable(self.game.player_produce))

                # generate cart
                cart = random.choice(self.game.get_combinations(self.game.player_produce[PLAYER],self.game.player_cash[self.game.active_player]))[1]

                self.game.buy_produce(PLAYER, cart)

                return BUYPRODUCE

            # Buy from warehouses
            elif action == BUYWARES:
                # choose player
                PLAYER = random.choice(self.game.who_buyable(self.game.player_wares))

                # generate cart
                cart = random.choice(self.game.get_combinations(self.game.player_wares[PLAYER],self.game.player_cash[self.game.active_player]))[1]

                self.game.buy_wares(PLAYER, cart)

                return BUYWARES

            elif action == AUCTION:
                self.game.start_auction()

                return AUCTION

    def get_bid(self, product):
        return random.randint(0,min(self.game.player_cash[self.playerID], sum(product)*10))

    # pricing policies
    # called by game() after buy action
    def factory_reprice(self):
        self.shufflePrices(self.game.player_produce[self.playerID],self.game.get_numFacts(),self.game.MIN_PROD_P,self.game.MAX_PROD_P)

    def warehouse_reprice(self,player,cart):
        self.shufflePrices(self.game.player_wares[self.playerID],self.game.player_warehouses[self.playerID],self.game.MIN_WARE_P,self.game.MAX_WARE_P)
        
    def shufflePrices(self,goods,cap, MIN, MAX):
        #drop overfloe
        total = 0
        for i in range(self.game.NUM_CONTAINERS):
            total += len(goods[i])
        
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
                else: goods[type][item] = random.randint(MIN,MAX)
                i += 1
            goods[type].sort()

    def accept_bid(self,bid,product,buyer,bids):
        if (bid > self.game.player_cash[self.playerID]): # NO CHOICE
            return True
        else:
            return (random.random() > 0.5)


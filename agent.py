import random

PRODUCE = 0
BUYPRODUCE = 1
BUYWARES = 2
AUCTION = 3
PASS = 4
SAILSEA = 5
BUYFACT = 6
BUYWAREHOUSE = 7

class Agent(object):
    def __init__(self,game,id):
        self.game = game
        self.playerID = id
        return

    # CALLED WHEN ITS PLAYERS TURN
    def make_move(self):
        return PASS

    # product: cargo being auctioned
    # output: integer value of what player is willing to pay
    def get_bid(self, product):
        return 0

    # Called if no price given upon buying
    # CALLED WHEN PLAYER IS ALLOWED TO REPRICE FACTORY PRODUCTS
    def factory_reprice(self):
        return

    # CALLED WHEN PLAYER IS ALLOWED TO REPRICE WAREHOUSE PRODUCTS
    def warehouse_reprice(self,player,cart):
        return

    # product: product being auctioned
    # bid: highest bid from players
    # output: true if player accepts bid false otherwise
    def accept_bid(self,bid,product,buyer,bids):
        return True


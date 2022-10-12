import random
import tkinter as tk
import time
from matplotlib import pyplot as plt
import numpy as np
import copy
import math
from multiprocessing import Process, Pipe
import datetime
import warnings
import pickle
import threading

from random2Agent import RandomAgent
from bestAgent import BestAgent
from history2Agent import HistoryAgent
from bestRandom2Agent import BestRandomAgent
from mctsAgent import MCTSAgent
from bestMCTSAgent import BestMCTSAgent
from histMCTSAgent import HistMCTSAgent
from cfrAgent import CFRAgent
import CFRNode

MAX_AUCTION_ROUNDS = 1 # for simplicity

PRODUCE = 0
BUYPRODUCE = 1
BUYWARES = 2
AUCTION = 3
PASS = 4
SAILSEA = 5
BUYFACT = 6
BUYWAREHOUSE = 7
ACTION_KEY = ["Produce","Buy Produce", "Buy Wares","Auction","Pass","Sail Sea","Buy Fact","Buy Warehouse"]
CONTAINER_COLOURS = ["RED", "GREEN", "BLUE", "BLACK", "WHITE"]

PERFECT = 0 # can see score cards
SEMI_PERFECT = 1 # info set limited
HIDDEN = 2

class Game(object):
    def __init__(self, num_players=3, ai=None, NUM_CONTAINERS=5, STARTING_FACTS=2, STARTING_WH=2,STARTING_CAPTIAL=10, anticheat=True, verbose=False, review=False, infomation = PERFECT, monopoly_mode = False, logfile="", infinity_mode = 0):
        self.AIs = ai

        # Game Type
        self.logfile = logfile
        self.infinity_mode = infinity_mode
        self.monopoly_mode = monopoly_mode # no doubling auctions + money each turn
        self.MONOPOLY_CASH = 2
        self.INFO_MODE = infomation 
        self.verbose = verbose
        self.review = review # draw game in window
        self.anticheat = anticheat # will check after each move if agent made invalid move

        self.NUM_PLAYERS = num_players
        self.NUM_CONTAINERS = NUM_CONTAINERS
        CONTAINERS_SUPPLY = 16 if not infinity_mode else 9999 #20*self.NUM_PLAYERS
        self.MIN_PROD_P = 1
        self.MAX_PROD_P = 4
        self.MIN_WARE_P = 2
        self.MAX_WARE_P = 5

        # Board State
        self.active_player = 0 #whose turn is it
        self.game_over = False
        self.turn_count = 0
        self.count = 0 # pass count

        self.supply = [CONTAINERS_SUPPLY for x in range(self.NUM_CONTAINERS)]
        self.player_cash = [STARTING_CAPTIAL for x in range(self.NUM_PLAYERS)]
        self.player_factories = [[0 for x in range(self.NUM_CONTAINERS)] for x in range(self.NUM_PLAYERS)] # index is colour, value is qty
        self.player_warehouses = [STARTING_WH for x in range(self.NUM_PLAYERS)]  # qty
        # self.player_produce[player][colour] is [priced at 1, price at 3 etc]
        self.player_produce = [[[] for x in range(self.NUM_CONTAINERS)] for x in range(self.NUM_PLAYERS)]  # price of each colour container []
        self.player_wares = [[[] for x in range(self.NUM_CONTAINERS)] for x in range(self.NUM_PLAYERS)]
        self.player_cargo = [[0 for x in range(self.NUM_CONTAINERS)] for x in range(self.NUM_PLAYERS)]  # {colour:qty}
        self.player_containers = [[0 for x in range(self.NUM_CONTAINERS)] for x in range(self.NUM_PLAYERS)]  # {colour:qty}
        self.player_cards = self.generate_card(MAX=10, MIN=2) # player score cards

        # Statistics of prices
        self.prod_log = [] # contains (turn0, price1, colour2, seller3, buyer4)
        self.ware_log = []
        self.auction_log = [] # contains (turn0, price1, bundle of product2, seller3, buyer4, [max bids by each player])
        self.history = [[] for x in range(self.NUM_PLAYERS)] # actions taken each turn

        # random starting factories
        """ for factories in self.player_factories: 
            factories[random.randint(0,self.NUM_CONTAINERS-1)] = 1 """
        # balanced factory colours 
        shuffle = [x for x in range(self.NUM_PLAYERS)]
        random.shuffle(shuffle)
        needed, extra = divmod(self.NUM_PLAYERS*STARTING_FACTS,self.NUM_CONTAINERS)
        storage = [needed for x in range(self.NUM_CONTAINERS)] # take from here randomly
        for x in random.sample(range(0, self.NUM_CONTAINERS),extra): storage[x] += 1 # only store what is needed
        for x in range(self.NUM_PLAYERS):
            count = 0
            while count != STARTING_FACTS:
                avaliable = [x for x in range(self.NUM_CONTAINERS)]
                choice = random.choice(avaliable)
                if storage[choice] != 0 and storage[choice] == max(storage): # no duplicates where possible
                    storage[choice] -= 1
                    self.player_factories[shuffle[x]][choice] += 1
                    count += 1
                else:
                    avaliable.remove(choice)
                    if len(avaliable) == 0:
                        print("\n\n\nError Selecting Factory")
                        print(self)
                        print("\n\n\n")
                        raise Exception("Error Selecting Factory")

        # # AGENT CLASSES
        self.players = [] # AGENT CLASSES
        if (ai):
            for x in range(len(ai)):
                if (ai[x] == "Random2Agent"): self.players.append(RandomAgent(self,x))
                elif (ai[x] == "BestRandom2Agent"): self.players.append(BestRandomAgent(self,x))
                elif (ai[x] == "BestAgent"): self.players.append(BestAgent(self,x))
                elif (ai[x] == "HistoryAgent"): self.players.append(HistoryAgent(self,x))
                elif (ai[x] == "MCTSAgent"): self.players.append(MCTSAgent(self,x))
                elif (ai[x] == "BestMCTSAgent"): self.players.append(BestMCTSAgent(self,x))
                elif (ai[x] == "HistMCTSAgent"): self.players.append(HistMCTSAgent(self,x))
                elif (ai[x] == "CFRAgent"): self.players.append(CFRAgent(self,x))
                else: 
                    print("ERROR UNKNOWN AGENT")
                    raise Exception("ERROR UNKNOWN AGENT")
        else:
            self.players = [RandomAgent(self,x) for x in range(num_players)]
        if (self.verbose):print(f"Players {ai}")

        # Draw Window
        if (self.review):
            top = tk.Tk()  
            top.geometry("1400x400")  
            
            self.cashLabel = []
            self.shipLabel = []
            self.cargoFrame = []
            self.cargoLabels = [[] for _ in range(self.NUM_PLAYERS)]
            self.warehouseLabel = []
            self.waresFrame = []
            self.waresLabels =  [[] for _ in range(self.NUM_PLAYERS)]
            self.factsFrame = []
            self.factsLabels = [[] for _ in range(self.NUM_PLAYERS)]
            self.produceFrame = []
            self.produceLabels = [[] for _ in range(self.NUM_PLAYERS)]
            self.containerFrame = []
            self.containerLabels = [[] for _ in range(self.NUM_PLAYERS)]
            self.scoreFrame = []

            # players
            for x in range(self.NUM_PLAYERS):
                labelframe1 = tk.LabelFrame(top, text="Player {} ({})".format(x,self.players[x].name), width=700) 
                labelframe1.pack(side="left",fill="both", expand="yes")
                
                # Cash
                self.cashLabel.append(tk.Label(labelframe1, text="Cash >> {}".format(self.player_cash[x])))  
                self.cashLabel[x].pack(side="top") 

                # Ship
                self.shipLabel.append(tk.Label(labelframe1, text="Ship at {}".format(self.player_ships[x]),pady=10))  
                self.shipLabel[x].pack(side="top") 

                # Ship Cargo
                self.cargoFrame.append(tk.Frame(labelframe1, height=20))
                self.cargoFrame[x].pack(side="top")

                # Warehouses
                self.warehouseLabel.append(tk.Label(labelframe1, text="Warehouses >> {}".format(self.player_warehouses[x]),pady=10))  
                self.warehouseLabel[x].pack(side="top") 

                # Wares
                self.waresFrame.append(tk.Frame(labelframe1, height=20))
                self.waresFrame[x].pack(side="top")

                # Factories
                self.factsFrame.append(tk.Frame(labelframe1))
                self.factsFrame[x].pack(side="top")
                tk.Label(self.factsFrame[x], text="Factories >> ",pady=10).pack(side="left")

                # Produce
                self.produceFrame.append(tk.Frame(labelframe1, height=20))
                self.produceFrame[x].pack(side="top")

                # Scored
                tk.Label(labelframe1, text="<< Scored >> ",pady=10).pack(side="top")
                self.containerFrame.append(tk.Frame(labelframe1))
                self.containerFrame[x].pack(side="top")

                # End Game Score
                self.scoreFrame.append(tk.Label(labelframe1,pady=10))
                self.scoreFrame[x].pack(side="top")

                # Hidden Score card
                for i in range(self.NUM_CONTAINERS):
                    label = tk.Label(labelframe1, text=f"${self.player_cards[x][i]}:", padx = 5)
                    label.pack(side="left")
                    label = tk.LabelFrame(labelframe1,bg=CONTAINER_COLOURS[i], height= 20, width=20)
                    label.pack(side="left")

            # Console
            self.consoleframe = tk.LabelFrame(top, text = "Console")  
            self.consoleframe.pack(side="top")  
            
            nextButton = tk.Button(self.consoleframe,text = "Next Move",command=self.make_move)  
            nextButton.pack()  

            nextButton = tk.Button(self.consoleframe,text = "Auto Play",command=self.auto_move)  
            nextButton.pack()

            #history
            self.draw_window()
            top.mainloop()

    def auto_move(self):
        self.timer = set_interval(self.make_move,0.1)
        
    # DISPLAY FUNCTIONS
    def __str__(self):
        for x in range(self.NUM_PLAYERS):
            print()
            print("Player {}".format(x))

            print("Cash {}".format(self.player_cash[x]))
            print("------------------------------------------")
            s = ""
            for i in range(len(self.player_factories[x])):  # factories player owns
                if self.player_factories[x][i] != 0:
                    s += CONTAINER_COLOURS[i] + "[{}] ".format(self.player_factories[x][i])
            print("Factories {}".format(s))

            s = ""
            for i in range(self.NUM_CONTAINERS):  # factory products player owns
                produce = self.player_produce[x][i]
                if produce != []:
                    s += CONTAINER_COLOURS[i] + str(produce) + " "
            print("Produce {}".format(s))
            print("------------------------------------------")
            print("Warehouses {}".format(self.player_warehouses[x]))

            s = ""
            for i in range(self.NUM_CONTAINERS):  # warehouse products player owns
                wares = self.player_wares[x][i]
                if wares != []:
                    s += CONTAINER_COLOURS[i] + str(wares) + " "
            """ for wares in self.player_wares[x]:  # warehouse products player owns
                for colours in range(len(wares)):  # warehouse products player owns
                    if wares[colours] != []:
                        print(wares,colours,CONTAINER_COLOURS)
                        s += CONTAINER_COLOURS[colours] + "[{}] ".format(wares[colours]) """
            print("Wares {}".format(s))
            print("------------------------------------------")
            s = ""
            for i in range(len(self.player_cargo[x])):  # cargo on player ship
                if self.player_cargo[x][i] != 0:
                    s += CONTAINER_COLOURS[i] + "[{}] ".format(self.player_cargo[x][i])
            print("Cargo {}".format(s))
            print("------------------------------------------")
            s = ""
            for i in range(len(self.player_containers[x])):  # containers on player island
                if self.player_containers[x][i] != 0:
                    s += CONTAINER_COLOURS[i] + "[{}] ".format(self.player_containers[x][i])
            print("Containers {}".format(s))

            s = ""
            for i in range(len(self.player_cards[x])):  # containers on player island
                s += CONTAINER_COLOURS[i] + "[{}] ".format(self.player_cards[x][i])
            print("Hidden Card {}".format(s))
        return ""

    def draw_window(self):
        for x in range(self.NUM_PLAYERS):
            self.cashLabel[x].config(text = "Cash >> {}".format(self.player_cash[x]))
            self.shipLabel[x].config(text = "Ship at {}".format(self.player_ships[x]))

            for _ in self.cargoLabels[x]:
                _.destroy()
            self.cargoLabels[x] = []
            for i in range(len(self.player_cargo[x])):
                if self.player_cargo[x][i] != 0:
                    label = tk.Label(self.cargoFrame[x], text=f"{self.player_cargo[x][i]}:", padx = 5)
                    label.pack(side="left")
                    self.cargoLabels[x].append(label)

                    label = tk.LabelFrame(self.cargoFrame[x],bg=CONTAINER_COLOURS[i], height= 20, width=20)
                    label.pack(side="left")
                    self.cargoLabels[x].append(label)

            self.warehouseLabel[x].config(text="Warehouses >> {}".format(self.player_warehouses[x]))

            for _ in self.waresLabels[x]:
                _.destroy()
            self.waresLabels[x] = []
            dic = reorganise(self.player_wares[x],CONTAINER_COLOURS)
            for price in dic.keys():
                label = tk.Label(self.waresFrame[x], text=f"${price}:", padx = 5)
                label.pack(side="left")
                self.waresLabels[x].append(label)
                for i in dic[price]:    
                    label = tk.LabelFrame(self.waresFrame[x],bg=i, height=20, width=20)
                    label.pack(side="left")
                    self.waresLabels[x].append(label)

            for _ in self.factsLabels[x]:
                _.destroy()
            self.factsLabels[x] = []
            for i in range(len(self.player_factories[x])):
                if self.player_factories[x][i] != 0:
                    label = tk.LabelFrame(self.factsFrame[x],bg=CONTAINER_COLOURS[i], height= 20, width=20)
                    label.pack(side="left")
                    self.factsLabels[x].append(label)

            for _ in self.produceLabels[x]:
                _.destroy()
            self.produceLabels[x] = []
            dic = reorganise(self.player_produce[x],CONTAINER_COLOURS)
            for price in dic.keys():
                label = tk.Label(self.produceFrame[x], text=f"${price}:", padx = 5)
                label.pack(side="left")
                self.produceLabels[x].append(label)
                for i in dic[price]:    
                    label = tk.LabelFrame(self.produceFrame[x],bg=i, height=20, width=20)
                    label.pack(side="left")
                    self.produceLabels[x].append(label)

            for _ in self.containerLabels[x]:
                _.destroy()
            self.containerLabels[x] = []
            for i in range(len(self.player_containers[x])):
                if self.player_containers[x][i] != 0:
                    label = tk.Label(self.containerFrame[x], text=f"{self.player_containers[x][i]}:", padx = 5)
                    label.pack(side="left")
                    self.containerLabels[x].append(label)

                    label = tk.LabelFrame(self.containerFrame[x],bg=CONTAINER_COLOURS[i], height= 20, width=20)
                    label.pack(side="left")
                    self.containerLabels[x].append(label)

    # Starts each turn
    # if move assume agents have already made a move (Used by MCTS for child node)
    def make_move(self, MOVE=-1):
        if (self.monopoly_mode): self.player_cash[self.active_player] += self.MONOPOLY_CASH
        move = self.players[self.active_player].make_move() if MOVE == -1 else MOVE
        self.history[self.active_player].append(move)
        self.pass_flag = move == PASS
        if (self.anticheat and self.player_cash[self.active_player] < 0): 
            print(f"\n\n\nCheat Detected. Negative Cash. After {ACTION_KEY[move]}")
            print(self)
            print("\n\n\n")
            raise Exception("Negative Cash")
        
        if (self.pass_flag): 
            self.count += 1
            if self.count >= self.NUM_PLAYERS:
                self.end_game(pass_end=True)
                if self.verbose: print("Game end due to passing") 
                return False
        else: self.count = 0

        self.active_player = (self.active_player+1) % self.NUM_PLAYERS

        # check if game over
        self.turn_count += 1
        if (self.infinity_mode and self.turn_count >= self.infinity_mode) or min(self.supply) <= 0: 
            self.end_game()
            return False

        if (self.review):
            self.draw_window()

        return True

    def end_game(self,pass_end=False):
        self.game_over = True
        self.final_score = self.final_scoring()

        # save to file
        if (self.logfile != ""):
            file = open(f"./log_{self.logfile}.txt","a") # write to 
            file.write(">")
            file.writelines(str(self.prod_log))
            file.write("-")
            file.writelines(str(self.ware_log))
            file.write("-")
            file.writelines(str(self.auction_log))
            file.write("-")
            data = []
            # merge all players actions into a unified game history
            for x in range(len(self.history[self.active_player])):
                for p in range(self.NUM_PLAYERS):
                    try:
                        data.append(self.history[p][x])
                    except:
                        pass
            file.writelines(str(data))
            file.write("-")
            if (pass_end): file.write("P")
            else: file.write("W")
            file.write("-")
            file.writelines(str(self.final_score))
            file.write("-")
            file.writelines(str(self.AIs))
            file.close() 

        if (self.verbose): print(self)

        if (self.review):
            for x in range(self.NUM_PLAYERS):
                self.scoreFrame[x].config(text = "Score >> {}".format(self.final_score[x]))

    # PLAYER ACTIONS
    def run_factory(self, NEW_PRODUCE = False):
        if self.anticheat: self.invalidAction(PRODUCE)

        self.player_cash[self.active_player] -= 1
        self.player_cash[(self.active_player-1)%self.NUM_PLAYERS] += 1

        # add containers
        if self.anticheat: before = self.player_produce[self.active_player]
        for i in range(self.NUM_CONTAINERS):
            num_facts = self.player_factories[self.active_player][i]
            if not NEW_PRODUCE or NEW_PRODUCE == -1:
                self.player_produce[self.active_player][i] += [1]*num_facts # default 1, reprice later
            self.supply[i] -= num_facts

        # pricing
        if not NEW_PRODUCE: 
            self.players[self.active_player].factory_reprice()
        elif NEW_PRODUCE != -1: # -1 special value for skipping reprice
            self.player_produce[self.active_player] = NEW_PRODUCE

        if self.anticheat and NEW_PRODUCE != -1: self.anticheat_Freprice(before, self.player_produce[self.active_player])

        if (self.verbose): print(">>>>> Player {} Running factories. Factory {} <<<<<".format(self.active_player,self.player_produce[self.active_player]))

    # buy from player
    # cart is list of tuples (colour, qty)
    def buy_produce(self, player, cart, NEW_WARES = False):
        if self.anticheat: 
            self.invalidAction(BUYPRODUCE)
            before = self.player_wares[self.active_player]
            if (cart == []):
                print("\n\n\nCheat Detected Buying Nothing. Attempted {}".format(id))
                print(self)
                print("\n\n\n")
                raise Exception("Buying Nothing")

        # cart stuff
        cost = 0
        for item in cart:
            # assumes list is sorted in desc price and players buy cheapest price
            for i in range(item[1]):
                if not NEW_WARES or NEW_WARES == -1:
                    self.player_wares[self.active_player][item[0]].append(2) # assume lowest warehouse price = 2
                price = self.player_produce[player][item[0]].pop(0)
                self.prod_log.append((self.turn_count,price,item[0],player,self.active_player))
                cost += price

        self.player_cash[self.active_player] -= cost
        self.player_cash[player] += cost

        # pricing
        if not NEW_WARES: self.players[self.active_player].warehouse_reprice(player,cart)
        elif NEW_WARES != -1: # -1 special value for skipping reprice
            self.player_wares[self.active_player] = NEW_WARES
        if self.anticheat and NEW_WARES != -1: self.anticheat_WHreprice(before, self.player_wares[self.active_player],cart)

        if (self.verbose): print(">>>>> Player {} Brought Produce {} From {}. Warehouse {} <<<<<".format(self.active_player, cart, player, self.player_wares[self.active_player]))

    def buy_wares(self, player, cart):
        if self.anticheat: 
            self.invalidAction(BUYWARES)
            if (cart == []):
                print("\n\n\nCheat Detected Buying Nothing. Attempted {}".format(id))
                print(self)
                print("\n\n\n")
                raise Exception("Buying Nothing")

        # cart stuff
        cost = 0
        for item in cart:
            self.player_cargo[self.active_player][item[0]] += item[1]
            # assumes list is sorted in desc price and players buy cheapest price
            for i in range(item[1]):
                price = self.player_wares[player][item[0]].pop(0)
                self.ware_log.append((self.turn_count,price,item[0],player,self.active_player))
                cost += price

        self.player_cash[self.active_player] -= cost
        self.player_cash[player] += cost

        if self.anticheat:
            if (self.player_cash[self.active_player] < 0):
                print("\n\n\nCheat Detected (-ve cash). Attempted {}".format(id))
                print(self)
                print("\n\n\n")
                raise Exception("-ve cash")

        if (self.verbose): print(">>>>> Player {} Brought Wares {} From {}. Ship {} <<<<<".format(self.active_player, cart, player, self.player_cargo[self.active_player]))

    def start_auction(self, starting_bids=np.array([])):
        if self.anticheat: self.invalidAction(AUCTION)
        bids = np.full(self.NUM_PLAYERS,-1) if starting_bids.size == 0 else starting_bids# bids made by player
        containers = self.player_cargo[self.active_player]
        if (self.verbose): print(">>>>> Player {} started auction of {} <<<<<".format(self.active_player,containers))

        # host auction
        highest_players = np.arange(self.NUM_PLAYERS) # start with everyone
        highest_bid = -1
        for i in highest_players:
            if i != self.active_player: 
                if bids[i] == -1: bids[i] = self.players[i].get_bid(containers)
                if (self.verbose): print("Player {} bid {}".format(i,bids[i]))
                if self.anticheat: 
                    if bids[i] > self.player_cash[i]: 
                        print("\n\n\nCheat Detected (Bid higher than cash on hand). Bid {} with {}".format(bids[i],self.player_cash[i]))
                        print(self)
                        print("\n\n\n")
                        raise Exception("Bid higher than cash on hand")
                if bids[i] > highest_bid: 
                    highest_players = [i]
                    highest_bid = bids[i]
                elif bids[i] == highest_bid: # tied players
                    highest_players.append(i)
        if (self.verbose): print("{} Tied Bid at {}".format(highest_players,highest_bid))

        # Check if still tied after auction
        if len(highest_players) != 1:
            highest_players = [random.choice(highest_players)]

        # must give highest players and bids since may be tied/some agents need the info
        if self.players[self.active_player].accept_bid(highest_bid,containers,highest_players[0],bids):
            # give players containers
            self.player_cash[highest_players[0]] -= highest_bid
            if (self.monopoly_mode): self.player_cash[self.active_player] += highest_bid
            else: self.player_cash[self.active_player] += highest_bid*2

            for i in range(self.NUM_CONTAINERS):
                #print(self.player_containers[highest_players[0]],containers)
                self.player_containers[highest_players[0]][i] += containers[i]

            if (self.verbose): print("Sold to player {} for {}".format(highest_players[0],highest_bid))
            self.auction_log.append((self.turn_count,highest_bid,containers,self.active_player,highest_players[0],bids))
        else:
            # self buy
            self.player_cash[self.active_player] -= highest_bid
            for i in range(self.NUM_CONTAINERS):
                self.player_containers[self.active_player][i] += containers[i]

            if (self.verbose): print("Self buy at {}".format(highest_bid))
            self.auction_log.append((self.turn_count,highest_bid,containers,self.active_player,self.active_player,bids))

        if self.anticheat:
            if len(self.auction_log) >= 2:
                if self.auction_log[-1][0] == self.auction_log[-2][0]:
                    print("AuctionLog error!")
                    raise Exception("AuctionLog error!")
            if (self.player_cash[self.active_player] < 0):
                print("\n\n\nCheat Detected (-ve cash). Attempted {}".format(id))
                print(self)
                print("\n\n\n")
                raise Exception("-ve cash")

        self.player_cargo[self.active_player] = [0 for x in range(self.NUM_CONTAINERS)]

    # resolve an auction with these params
    # used by search nodes in MCTS
    def resolve_auction(self, seller, buyer, containers, bids):
        highest_bid = max(bids)
        if seller == buyer:
            # self buy
            self.player_cash[self.active_player] -= highest_bid
            for i in range(self.NUM_CONTAINERS):
                self.player_containers[self.active_player][i] += containers[i]

            self.auction_log.append((self.turn_count,highest_bid,containers,self.active_player,self.active_player,bids))

        else:
            # give players containers
            self.player_cash[buyer] -= highest_bid
            if (self.monopoly_mode): self.player_cash[self.active_player] += highest_bid
            else: self.player_cash[self.active_player] += highest_bid*2

            for i in range(self.NUM_CONTAINERS):
                self.player_containers[buyer][i] += containers[i]

            self.auction_log.append((self.turn_count,highest_bid,containers,self.active_player,buyer,bids))

        self.player_cargo[self.active_player] = [0 for x in range(self.NUM_CONTAINERS)]
        
        if self.anticheat:
            if len(self.auction_log) >= 2:
                if self.auction_log[-1][0] == self.auction_log[-2][0]:
                    print("AuctionLog error!")
                    raise Exception("AuctionLog error!")

    # ANTI CHEAT FUNCTIONS
    # valid move categories
    def get_moves(self):
        valid = [PASS]
        
        #can run factory?
        if (self.player_cash[self.active_player] >= 1):
            valid.append(PRODUCE)
        
        for i in range(self.NUM_PLAYERS):
            #is there products to buy?
            if (i != self.active_player and self.is_combinations(self.player_produce[i],self.player_cash[self.active_player])):
                valid.append(BUYPRODUCE)
                break
            
        for i in range(self.NUM_PLAYERS):
            #is there wares to buy?
            if (i != self.active_player and self.is_combinations(self.player_wares[i],self.player_cash[self.active_player])):
                valid.append(BUYWARES)
                break

        #can start auction?
        if (self.player_cargo[self.active_player] != [0 for x in range(self.NUM_CONTAINERS)]):
            valid.append(AUCTION)

        return valid

    def invalidAction(self,id):
        # is that even a vlid move
        if (id not in self.get_moves()):
            valid = []
            print(f"Active player {self.active_player}")
            for i in range(self.NUM_PLAYERS):
                combi = self.is_combinations(self.player_wares[i],self.player_cash[self.active_player])
                print(f"player {i}, wares {self.player_wares[i]} cash {self.player_cash[self.active_player]} is combi {combi}")
                if (i != self.active_player and combi):
                    valid.append(BUYWARES)
                    break
            for i in range(self.NUM_PLAYERS):
                combi = self.is_combinations(self.player_produce[i],self.player_cash[self.active_player])
                print(f"player {i}, produce {self.player_produce[i]} cash {self.player_cash[self.active_player]} is combi {combi}")
                if (i != self.active_player and combi):
                    valid.append(BUYPRODUCE)
                    break
            print("\n\n\nCheat Detected. Attempted {} in {}".format(id,self.get_moves()))
            print(self)
            print("\n\n\n")
            raise Exception("Invalid action")

    # BEFORE is the active player's wares before buy produce action was taken
    # BROUGHT is list of tuples (colour, qty)
    def anticheat_WHreprice(self, BEFORE, AFTER, BROUGHT):
        count = [0 for x in range(self.NUM_CONTAINERS)]
        for i in range(self.NUM_CONTAINERS):
            count[i] += len(BEFORE[i])

        after = [0 for x in range(self.NUM_CONTAINERS)]
        for i in range(self.NUM_CONTAINERS):
            after[i] += len(AFTER[i])

        total_warehouse = self.player_warehouses[self.active_player]

        check = copy.copy(count)
        for colour,qty in BROUGHT: # technically shoudl just check after[i] > check[i] here really
            check[colour] += qty

        VALID_PRICE = True
        for i in range(self.NUM_CONTAINERS):
            if after[i] > check[i]: # created more containers than possible
                VALID_PRICE = False
                break

        if(sum(after) > total_warehouse*2):
            print("\n\n\nCheat Detected. Warehouse overflow \n Warehouse count {} \nproduce {}".format(total_warehouse,self.player_produce[self.active_player]))
            print(self)
            print("\n\n\n")
            raise Exception("Warehouse overflow")

        if(after != count and sum(after) != total_warehouse*2):
            print("\n\n\nCheat Detected. Warehouse reprice num container mismatch \n Before {} \nAfter {}".format(count,after))
            print(self)
            print("\n\n\n")
            raise Exception("Warehouse reprice num container mismatch")

        if not VALID_PRICE and sum(after) != min(total_warehouse*2,sum(count)+total_warehouse): # cannot drop more containers?
            print("\n\n\nCheat Detected. Containers NEW_WARES is invalid \n Before {} \nAfter {}".format(count,after))
            print(self)
            print("\n\n\n")
            raise Exception("Containers NEW_WARES is invalid")

        for x in AFTER:
            if x and min(x) < self.MIN_WARE_P and max(x) > self.MAX_WARE_P:
                print("\n\n\nCheat Detected. WAREHOUSE PRICING OUT OF RANGE \nAfter {}".format(after))
                print(self)
                print("\n\n\n")
                raise Exception("WAREHOUSE PRICING OUT OF RANGE")

    def anticheat_Freprice(self, BEFORE, AFTER):
        count = [0 for x in range(self.NUM_CONTAINERS)]
        for i in range(self.NUM_CONTAINERS):
            count[i] += len(BEFORE[i])

        after = [0 for x in range(self.NUM_CONTAINERS)]
        for i in range(self.NUM_CONTAINERS):
            after[i] += len(AFTER[i])

        total_facts = 0
        possible = copy.copy(count)
        for i in range(self.NUM_CONTAINERS):
            total_facts += self.player_factories[self.active_player][i]
            possible[i] += self.player_factories[self.active_player][i]

        VALID_PRICE = True
        for i in range(self.NUM_CONTAINERS):
            if after[i] > possible[i]: # created more containers than possible
                VALID_PRICE = False
                break

        if(sum(after) > total_facts*2):
            print("\n\n\nCheat Detected. Factory overflow \n Fact count {} \nproduce {}".format(total_facts,self.player_produce[self.active_player]))
            print(self)
            print("\n\n\n")
            raise Exception("Factory overflow ")

        if(after != count and sum(after) != total_facts*2):
            print("\n\n\nCheat Detected. Factory reprice num container mismatch \n Before {} \nAfter {}".format(count,after))
            print(self)
            print("\n\n\n")
            raise Exception("Factory reprice num container mismatch")

        
        if not VALID_PRICE and sum(after) != min(total_facts*2,sum(count)+total_facts): # cannot drop more containers?
            print("\n\n\nCheat Detected. Containers NEW_PRODUCE is invalid \n Before {} \nAfter {}".format(count,after))
            print(self)
            print("\n\n\n")
            raise Exception("Containers NEW_PRODUCE is invalid")

        for x in AFTER:
            if x and min(x) < self.MIN_WARE_P and max(x) > self.MAX_WARE_P:
                print("\n\n\nCheat Detected. WAREHOUSE PRICING OUT OF RANGE \nAfter {}".format(after))
                print(self)
                print("\n\n\n")
                raise Exception("WAREHOUSE PRICING OUT OF RANGE")

    #dic is either wares or produce
    def who_buyable(self, dic):
        choice = []
        for i in range(self.NUM_PLAYERS):
            if (i != self.active_player and self.is_combinations(dic[i],self.player_cash[self.active_player])):
                choice.append(i)

        return choice

    # HELPER FUNCTIONS
    def get_numFacts(self):
        total_facts = 0
        for i in range(self.NUM_CONTAINERS):
            total_facts += self.player_factories[self.active_player][i]
        return total_facts

    def get_numWarehouses(self):
        return self.player_warehouses[self.active_player]

    #return total number of containers sold at factories by player
    def ware_sale_count(self, player):
        count = 0
        for x in self.game.ware_log: #(turn0, price1, colour2, seller3, buyer4)
            if x[4] == self.playerID:
                buy_count += 1
        return count

    # value from scorecard for player for given containers
    def containers_score(self,player,containers):
        value = 0
        for x in range(self.NUM_CONTAINERS):
            value += containers[x]*self.player_cards[player][x]
        return value

    #[[[] for x in range(self.NUM_CONTAINERS)] for x in range(self.NUM_PLAYERS)][player]
    def get_numProduce(self,player = None):
        if (player == None): player = self.active_player
        count = 0
        for x in self.player_produce[player]:
            count += len(x)
        return count

    def get_numWares(self,player = None):
        if (player == None): player = self.active_player
        count = 0
        for x in self.player_wares[player]:
            count += len(x)
        return count
    
    def final_scoring(self):
        if (self.verbose): print("\n\n\n")
        scores = []
        for x in range(self.NUM_PLAYERS):
            if (self.verbose): 
                print()
                print("<<<<< Player {} >>>>>".format(x))
            score = 0

            # score for containers on island
            if (self.verbose): print("Score Card {}".format(self.player_cards[x]))
            for i in range(len(self.player_containers[x])):
                score += self.player_cards[x][i]*self.player_containers[x][i]
                if (self.verbose):  print("{} {} x{} -> {}".format(self.player_containers[x][i],CONTAINER_COLOURS[i],self.player_cards[x][i],self.player_cards[x][i]*self.player_containers[x][i]))

            # score for containers in cargo ship
            total = 0
            for i in range(len(self.player_cargo[x])):
                total += self.player_cargo[x][i]
            score += total*2
            if (self.verbose): print("Container in Ship {} -> Score {}".format(total, total*2))

            # score for containers in warehouse
            total = self.get_numWares(x)
            score += total*2
            if (self.verbose): print("Container in Warehouse {} -> Score {}".format(total, total*2))

            # score for containers in factories
            total = self.get_numProduce(x)
            score += total
            if (self.verbose): print("Container in Factory {} -> Score {}".format(total, total*1))

            # score for cash in hand
            if (self.verbose): print("Cash in hand {}".format(self.player_cash[x]))
            score += self.player_cash[x]

            if (self.verbose): print("Final Score {}".format(score))
            scores.append(score)
        
        return scores
            
    # input [(colour,qty),...], used in combination
    # output [red qty, blue qty, ...], used in auctions
    def cart_to_auction(self,input):
        out = [0 for x in range(self.NUM_CONTAINERS)]
        for x in input:
            out[x[0]] += x[1]
        return out

    def auction_to_cart(self,input):
        out = []
        for i in range(len(input)):
            if input[i] != 0: out.append((i,input[i]))
        return out

    # from a specific player's offers, create all permutations with costing up to cash
    # goods is a list of container prices sold for each colour [red, blue, green], red = [4,5,5]
    # output is list of list of [cost, [(colour, qty),...]]
    def get_combinations(self, goods, cash):
        return self.combi(0,goods,cash)[1:] # first item is blank

    def is_combinations(self,goods,cash):
        return (self.combi(0,goods,cash,True) == True)

    def combi(self,i,goods,cash,earlystop=False): #early stop is just to check if there is combination
        if i >= len(goods):
            return [(0,[])]
        
        else:
            prev = self.combi(i+1,goods,cash)
            if(earlystop and len(prev) > 1): return True
            next = prev.copy()
            for item in prev:
                for amt in range(1,len(goods[i])+1):
                    cost = item[0] + sum(goods[i][:amt])
                    if (cost < cash):
                        next.append((cost,item[1]+[(i,amt)])) #assumes only buy lowest cost
                        #next.append((cost,item[1]+goods[i][:amt]))
            return next

    def generate_card(self, MAX=10, MIN=2, GET_COMBI=False):
        score = np.linspace(MIN,MAX,num=self.NUM_CONTAINERS,dtype="int").tolist()
        scores = []

        """ # deterministic
        scores = [
            [10,2,4,6,5],
            [5,10,2,4,6],
            [6,5,10,2,4],
            [4,6,5,10,2],
            [2,4,6,5,10],
        ] """

        for x in range(self.NUM_CONTAINERS):
            scores.append(copy.copy(score))
            score.append(score[0]) #move from to back
            del score[0]
        random.shuffle(scores)
        return scores[:self.NUM_PLAYERS] if not GET_COMBI else scores

# copy paste
def set_interval(func, sec):
    def func_wrapper():
        if(func()): # only if true
            set_interval(func, sec)
    t = threading.Timer(sec, func_wrapper)
    t.start()
    return t

# Sort products by price rather than by colour
# reorganise red:[2,6], black: [2,3] into 2:[red,black], 6:[red] 3:[black]
# for ui
def reorganise(arr,colours):
    out = {}
    for x in range(len(colours)):
        for price in arr[x]:
            if price in out:
                out[price].append(colours[x])
            else:
                out[price] = [colours[x]]
    return out

# 3 player pipeline
def test3_pipeline(candidate, NUM_SIMS = 500, notes="", THREAD = True, config = False):
    if not config:
        config = {
            "review" : False, # show graphical ui
            "verbose" : False, # print game info to console
            "anticheat" : False, # checks if players cheat every turn
            
            # Gamemodes
            "monopoly_mode": True,
            "infinity_mode": 100,
            "infomation": PERFECT,
            "num_players":3,

            # Starting Conditions
            "NUM_CONTAINERS":3,
            "STARTING_FACTS":2,
            "STARTING_WH":2,
            "STARTING_CAPTIAL":10,
        }
    else:
        config = config
    print("Game Settings",config)
    
    # MODES -> regular , monopoly (zero-sum)
    # MODIFIERS -> limited, infinity (capped by turn timer)
    # INFO_MODE -> perfect, partial, none 
    print(f"TESTING {candidate} {notes}")
    start_time = time.time()

    INFO = config["infomation"]

    # Exploit test
    # 3 Random, 1 Test
    run_games(f"2Rand_1{candidate}I{INFO}",config,[candidate,"Random2Agent","Random2Agent"],NUM_SIMS,results_log=notes,THREAD=THREAD)

    # Equilibrium Test
    # 3 Best, 1 Test
    run_games(f"2Best_1{candidate}I{INFO}",config,[candidate,"BestAgent","BestAgent"],NUM_SIMS,results_log=notes,THREAD=THREAD)

    # Follower Test
    # 1 Test, 3 History
    run_games(f"2History_1{candidate}I{INFO}",config,[candidate,"HistoryAgent","HistoryAgent"],NUM_SIMS,results_log=notes,THREAD=THREAD)
    
    # Equilibrium Test 2
    # 1 Best, 3 Test
    run_games(f"1Best_2{candidate}I{INFO}",config,[candidate,candidate,"BestAgent"],int(NUM_SIMS/2),results_log=notes,THREAD=THREAD)

    # Follower Test
    # 1 History, 3 Test
    run_games(f"1History_2{candidate}I{INFO}",config,[candidate,candidate,"HistoryAgent"],int(NUM_SIMS/2),results_log=notes,THREAD=THREAD)

    print("Experiments Ended ({:.2f} mins)".format((time.time()-start_time)/60))

def game_thread(THREAD_ID,conn,config,PLAYERS,num_games):
    PLAYER_SHUFFLE = True
    percent = math.ceil(num_games*0.10)
    num_players = len(PLAYERS)
    OUTPUT = []

    for num_game in range(num_games):
        shuffle = [x for x in range(num_players)] # index is player id, value is position in game
        if (PLAYER_SHUFFLE): random.shuffle(shuffle)
        game = Game(**config, ai = [PLAYERS[x] for x in shuffle])
        while not game.game_over:
            game.make_move()

        OUTPUT.append((shuffle,game))
        
        if (num_game%percent == 0): print(f"Thread {THREAD_ID}, Game {num_game+1}/{num_games}")
    
    conn.send(OUTPUT)
    conn.close()

def run_games(testname, config, PLAYERS, num_games = 1,results_log="", THREAD = True):
    now = datetime.datetime.now()
    print(f"[Experiment {num_games} games] {testname} {now.strftime('%H:%M:%S')}")
    config["logfile"] = testname
    num_players = len(PLAYERS)
    SF = 5 # sig figures for display
    move_types = 8 # different types of moves
    ProduceCost = 1

    # wr[player][0] is number of times player came in 1st
    wr = [[0 for x in range(num_players)] for x in range(num_players)]
    shuffle = [x for x in range(num_players)] # index is player id, value is position in game

    # Statistics
    scores = [[] for x in range(num_players)]
    norm_scores = [[] for x in range(num_players)]
    move_policy = [[[] for y in range(move_types)] for x in range(num_players)] # % of each action

    # Maufacture = sale - produce, WH = sale - purchase, Auction = sale - purchase || value - purchase
    # per container profit
    pcp_produce = [[] for x in range(num_players)]
    pcp_wares = [[] for x in range(num_players)]
    pcp_sell_auction = [[] for x in range(num_players)]
    pcp_buy_auction = [[] for x in range(num_players)]

    pcp_produce_cost = [[] for x in range(num_players)]
    pcp_produce_rev = [[] for x in range(num_players)]
    pcp_wares_cost = [[] for x in range(num_players)]
    pcp_wares_rev = [[] for x in range(num_players)]
    pcp_auction_cost = [[] for x in range(num_players)]
    pcp_auction_rev = [[] for x in range(num_players)]

    profits_percent = [[[] for y in range(num_players)] for x in range(4)] # prod, wares, sell, buy auction profit %
    auction_overbid = [[] for x in range(num_players)] # overbid in each auction
    game_length = []
    containers_produced = [] # sold in auctions (ignores dropped goods)
    auction_selfbuy = [[] for x in range(num_players)] # % of self buys in each auction

    start_time = time.time()

    if THREAD:
        NUM_THREADS = min(int(num_games),10)
        THREADS = []
        THREAD_PIPES = []
        THREAD_DATA = []
        for x in range(NUM_THREADS):
            parent_conn, child_conn = Pipe()
            THREAD_PIPES.append(parent_conn)
            THREADS.append(Process(target=game_thread, args=(x,child_conn,config,PLAYERS,round(num_games/NUM_THREADS))))
            THREADS[x].start()

        for x in range(NUM_THREADS):
            THREAD_DATA += THREAD_PIPES[x].recv()
            THREADS[x].join()
    else:
        THREAD_DATA = []
        PLAYER_SHUFFLE = True
        percent = math.ceil(num_games*0.10)
        num_players = len(PLAYERS)

        for num_game in range(num_games):
            shuffle = [x for x in range(num_players)] # index is player id, value is position in game
            if (PLAYER_SHUFFLE): random.shuffle(shuffle)
            game = Game(**config, ai = [PLAYERS[x] for x in shuffle])
            while not game.game_over:
                #if(game.verbose): print(game)
                #time1 = time.time()
                game.make_move()
                #print(f"Turn {game.turn_count} {abs(time1 - time.time())} secs")
            THREAD_DATA.append((shuffle,game))
            
            if (num_game%percent == 0): print(f"Game {num_game+1}/{num_games}")
        
    # Consolidate data
    # Collect Statistics NOTE: have to reallocate all colours that comes from game. shuffle[x]
    for shuffle,game in THREAD_DATA:
        game_length.append(game.turn_count)
        #for x in game.prod_log: #(turn0, price1, colour2, seller3, buyer4)
        selfbuy_count = [0 for x in range(num_players)]
        auction_count = [0 for x in range(num_players)] 
        overbid_count = [[] for x in range(num_players)]
        containers_count = 0 # total scored containers
        containers_zones = [[0,0,0] for x in range(num_players)] # num containers produced, warehoused, auctioned by each player as seller
        history_count = [[0 for y in range(move_types)] for x in range(num_players)]
        sell_auction = [0 for x in range(num_players)] # gains from being a seller
        buy_auction_profits = [0 for x in range(num_players)] # gain - cost from being a buyer
        earned_prod = [0 for x in range(num_players)] # earned on selling produce
        spent_prod = [0 for x in range(num_players)]  
        earned_ware = [0 for x in range(num_players)]
        spent_ware = [0 for x in range(num_players)]

        # all stats are calc in AI (!= pos in game)
        # SHUFFLE[pos] -> AI
        # UNSHUFFLE[AI] -> pos in game
        for x in game.auction_log: # (turn0, price1, bundle of product2, seller3, buyer4, [max bids by each player])
            SELLER = shuffle[x[3]]
            BUYER = shuffle[x[4]]

            auction_count[SELLER] += 1
            containers_zones[SELLER][2] += sum(x[2]) # num container sold by player in auction
            if SELLER != BUYER:
                temp = x[5]
                temp[x[4]] = 0
                overbid_count[BUYER].append(x[1]-max(temp)) # paid - 2nd highest bid
                if game.monopoly_mode: sell_auction[SELLER] += x[1]
                else: sell_auction[SELLER] += x[1]*2
                buy_auction_profits[BUYER] += game.containers_score(x[4],x[2]) - x[1] #gain in score - bid

            else: # seller is buyer
                selfbuy_count[SELLER] += 1
                sell_auction[SELLER] += game.containers_score(x[3],x[2]) - x[1] #gain in score - selfbuy cost
                
        for x in range(num_players):
            if overbid_count[x] != []: auction_overbid[x].append(np.mean(overbid_count[x]))
            if auction_count[x] != 0: auction_selfbuy[x].append(selfbuy_count[x]/auction_count[x])
            containers_count += sum(game.player_containers[x])
            for i in game.history[x]: history_count[shuffle[x]][i] += 1

            # score leftover containers at end of game
            for c in range(game.NUM_CONTAINERS):
                earned_prod[shuffle[x]] += len(game.player_produce[x][c])
                containers_zones[shuffle[x]][0] += len(game.player_produce[x][c]) # "sell" leftovers
                earned_ware[shuffle[x]] += len(game.player_wares[x][c])*2
                containers_zones[shuffle[x]][1] += len(game.player_wares[x][c]) # "sell" leftovers
            sell_auction[shuffle[x]] += sum(game.player_cargo[x])*2
            containers_zones[shuffle[x]][2] += sum(game.player_cargo[x]) # "sell" leftovers
        containers_produced.append(containers_count)

        #print("Shuffle",shuffle)
        #print(containers_zones)
        for x in game.prod_log: # contains (turn0, price1, colour2, seller3, buyer4)
            earned_prod[shuffle[x[3]]] += x[1]
            spent_prod[shuffle[x[4]]] += x[1]
            containers_zones[shuffle[x[3]]][0] += 1 # num container sold by player in Factory
        for x in game.ware_log:
            earned_ware[shuffle[x[3]]] += x[1]
            spent_ware[shuffle[x[4]]] += x[1]
            containers_zones[shuffle[x[3]]][1] += 1 # num container sold by player in WH

        # Maufacture = sale - produce, WH = sale - purchase, Auction = sale - purchase || (value - bid) - purchase
        produce_profits = [0 for x in range(num_players)]
        wares_profits = [0 for x in range(num_players)]
        sell_auction_profits = [0 for x in range(num_players)]
        for x in range(num_players):
            # calc profits
            """ print(f"Player {x} Hist {history_count[x]}")
            print(f"Player {x} Prod {game.player_produce[shuffle.index(x)]}")
            print("ProdLog",shuffle.index(x),game.prod_log)
            print(f"Player {x} Wares {game.player_wares[shuffle.index(x)]}")
            print("ProdLog",game.ware_log)
            print(f"Player {x} Zone {containers_zones[x]}\n") """

            temp = sum(history_count[x])
            for i in range(len(history_count[x])): move_policy[x][i].append(history_count[x][i]/temp)

            profit_total = 0
            produce_profits[x] = earned_prod[x] - history_count[x][0]*ProduceCost
            profit_total += produce_profits[x]
            if history_count[x][0] != 0 and containers_zones[x][0] != 0: pcp_produce[x].append(produce_profits[x]/containers_zones[x][0])
            wares_profits[x] = earned_ware[x] - spent_prod[x]
            profit_total += wares_profits[x]
            if history_count[x][1] != 0 and containers_zones[x][1] != 0: pcp_wares[x].append(wares_profits[x]/containers_zones[x][1])
            sell_auction_profits[x] = sell_auction[x] - spent_ware[x] # seller in auction (bid offer + self buy)
            profit_total += sell_auction_profits[x]
            profit_total += buy_auction_profits[x]

            if sum(game.player_containers[shuffle.index(x)]) != 0: # DIDNT SCORE ANY CONTAINERS
                pcp_buy_auction[x].append(buy_auction_profits[x]/sum(game.player_containers[shuffle.index(x)]))
            if history_count[x][2] != 0 and containers_zones[x][2] != 0: # NEVER BROUGHT WARES
                pcp_sell_auction[x].append(sell_auction_profits[x]/containers_zones[x][2])
                pcp_auction_cost[x].append(spent_ware[x]/containers_zones[x][2])
                pcp_auction_rev[x].append(sell_auction[x]/containers_zones[x][2])
            if history_count[x][1] != 0 and containers_zones[x][1] != 0: # NEVER BROUGHT PRODUCE
                pcp_wares_cost[x].append(spent_prod[x]/containers_zones[x][1])
                pcp_wares_rev[x].append(earned_ware[x]/containers_zones[x][1])
            if history_count[x][0] != 0 and containers_zones[x][0] != 0: # NEVER PRODUCED
                pcp_produce_cost[x].append(history_count[x][0]*ProduceCost/containers_zones[x][0])
                pcp_produce_rev[x].append(earned_prod[x]/containers_zones[x][0])

            if (profit_total != 0):
                profits_percent[0][x].append(produce_profits[x]/profit_total)
                profits_percent[1][x].append(wares_profits[x]/profit_total)
                profits_percent[2][x].append(sell_auction_profits[x]/profit_total)
                profits_percent[3][x].append(buy_auction_profits[x]/profit_total)

        # Game Scores
        score = game.final_score
        temp = []
        for x in range(num_players): # x in position in game, p is AI associated
            p = shuffle[x]
            scores[p].append(score[x])
            # Sort players by their score
            temp.append((score[x], p))
        temp.sort(key = lambda x: x[0], reverse=True)
        for x in range(num_players):
            data = temp[x]
            if (temp[-1][0] == temp[0][0]): # all players same score
                wr[data[1]][0] += 1 # if tied all last place
                norm_scores[data[1]].append(0)
                continue
            else:
                wr[data[1]][x] += 1 # track rank of player
                norm_scores[data[1]].append((temp[x][0]-temp[-1][0])/(temp[0][0]-temp[-1][0]))

    # Simulation results
    file = open(f"./EXPERIMENT_DATA_{results_log}.txt","a")
    file.write(f"[Experiment {num_games} games] {testname} {now.strftime('%m/%d/%Y, %H:%M:%S')}\n")
    warnings.filterwarnings('ignore') # mean of empty list results in error
    file.write("Sim Ended ({:.2f} mins)\n".format((time.time()-start_time)/60))
    file.write(f"Length > \t{round(np.mean(game_length),SF)} \t[std] {round(np.std(game_length),SF)}] Turns\n")
    file.write(f"Auctioned > \t{round(np.mean(containers_produced),SF)} \t[std] {round(np.std(containers_produced),SF)} Containers\n")
    file.write(f"SelfBuy %> \t{str([round(np.mean(x),SF) for x in auction_selfbuy]):50} [std] {[round(np.std(x),SF) for x in auction_selfbuy]}\n")
    file.write(f"Overbid > \t{str([round(np.mean(x),SF) for x in auction_overbid]):50} [std] {[round(np.std(x),SF) for x in auction_overbid]}\n")
    file.write("\n")
    file.write(f"PCP Produce > \t{str([round(np.mean(x),SF) for x in pcp_produce]):50} [std] {[round(np.std(x),SF) for x in pcp_produce]}\n")
    file.write(f"PCP Wares > \t{str([round(np.mean(x),SF) for x in pcp_wares]):50} [std] {[round(np.std(x),SF) for x in pcp_wares]}\n")
    file.write(f"PCP SellAuct > \t{str([round(np.mean(x),SF) for x in pcp_sell_auction]):50} [std] {[round(np.std(x),SF) for x in pcp_sell_auction]}\n")
    file.write(f"PCP BuyAuct > \t{str([round(np.mean(x),SF) for x in pcp_buy_auction]):50} [std] {[round(np.std(x),SF) for x in pcp_buy_auction]}\n")
    file.write("\n")
    file.write(f"Produce Rev > \t{str([round(np.mean(x),SF) for x in pcp_produce_rev]):50} [std] {[round(np.std(x),SF) for x in pcp_produce_rev]}\n")
    file.write(f"Produce Cost > \t{str([round(np.mean(x),SF) for x in pcp_produce_cost]):50} [std] {[round(np.std(x),SF) for x in pcp_produce_cost]}\n")
    file.write(f"Wares Rev > \t{str([round(np.mean(x),SF) for x in pcp_wares_rev]):50} [std] {[round(np.std(x),SF) for x in pcp_wares_rev]}\n")
    file.write(f"Wares Cost > \t{str([round(np.mean(x),SF) for x in pcp_wares_cost]):50} [std] {[round(np.std(x),SF) for x in pcp_wares_cost]}\n")
    file.write(f"SellAuct Rev > \t{str([round(np.mean(x),SF) for x in pcp_auction_rev]):50} [std] {[round(np.std(x),SF) for x in pcp_auction_rev]}\n")
    file.write(f"SellAuct Cost> \t{str([round(np.mean(x),SF) for x in pcp_auction_cost]):50} [std] {[round(np.std(x),SF) for x in pcp_auction_cost]}\n")
    file.write("\n")
    file.write(f"% Produce> \t{str([round(np.mean(x),SF) for x in profits_percent[0]]):50} [std] {[round(np.std(x),SF) for x in profits_percent[0]]}\n")
    file.write(f"% Wares> \t{str([round(np.mean(x),SF) for x in profits_percent[1]]):50} [std] {[round(np.std(x),SF) for x in profits_percent[1]]}\n")
    file.write(f"% SellAuct> \t{str([round(np.mean(x),SF) for x in profits_percent[2]]):50} [std] {[round(np.std(x),SF) for x in profits_percent[2]]}\n")
    file.write(f"% BuyAuct> \t{str([round(np.mean(x),SF) for x in profits_percent[3]]):50} [std] {[round(np.std(x),SF) for x in profits_percent[3]]}\n")
    
    for x in range(num_players):
        file.write("\nPlayer {}, Placements {}, Avg Score {:.2f} [std] {:.2f}, Avg Normalised Score {:.2f}, [std] {:.2f}\n".format(PLAYERS[x],wr[x], np.mean(scores[x]),np.std(scores[x]), np.mean(norm_scores[x]),np.std(norm_scores[x])))
        for i in range(move_types):
            if i in [SAILSEA,BUYFACT,BUYWAREHOUSE]: continue #blacklisted actions (sail, buy fact & WH)
            file.write(f" {ACTION_KEY[i]} > \t{round(np.mean(move_policy[x][i]),SF)} [std {round(np.std(move_policy[x][i]),SF)}] \n")#, end="\n" if i%3==2 else "")
    file.write("\n")
    file.close()

# CFR Nodes
def display_results(i_map,number = 50):
    print()
    print('Strategies:')
    sorted_items = sorted(i_map.items(), key=lambda x: x[1].explored, reverse=True)
    count = 0
    for v in sorted_items:
        print(v[1])
        count += 1
        if count > number:
            break
    print()

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

    test3_pipeline("CFRAgent",100,notes = "Test", THREAD=False, config = config) # if strategy file for CFR is big dont thread
    #test3_pipeline("MCTSAgent",500,notes = "BaseMCTS")#, config = config)
    #test3_pipeline("HistMCTSAgent",200,notes = "HistMCTS")
    #run_games(f"",config,["CFRAgent","Random2Agent","Random2Agent"],100,results_log="", THREAD=False)#, THREAD=False)
    exit()
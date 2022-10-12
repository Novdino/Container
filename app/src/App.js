import './App.css';
import { useState } from "react";
const CONTAINER_COLOURS = ["RED", "GREEN", "BLUE", "BLACK", "WHITE"]
const ALT_COLOURS = ["beige", "greenyellow", "AQUA", "GREY", "red"]
const ACTION_KEY = ["Produce","Buy Produce", "Buy Wares","Auction","Pass","Sail Sea","Buy Fact","Buy Warehouse"]
const PLAYERS = [0,1,2,3]

function App() {
  const [gameData, setGameData] = useState("");
  const [NUM_GAMES, setNUMGAMES] = useState(100);
  const [TYPE, setTYPE] = useState(0);
  const [FOCUS_TURN, setTURN] = useState(0);
  const [gameID, setGameID] = useState(1);
  const [POV, setPOV] = useState(0);

  let showFile = async (e) => {
    e.preventDefault()
    const reader = new FileReader()
    reader.onload = async (e) => { 
      const text = (e.target.result);
      //console.log(text);
      let games = text.split('>');
      setGameData(games);
      setNUMGAMES(games.length-1);
    };
    reader.readAsText(e.target.files[0])
  }

  let PRODUCE = [];
  let WARES = [];
  let AUCTION = [];
  let HISTORY = [];
  let VICTORY = [];
  if (gameData != "" && gameID != 0 && gameID <= NUM_GAMES && gameID > 0){
    let data = gameData[gameID].replaceAll('array\(','').replaceAll('\)\)',')').replaceAll('-1','_')
    data = data.split('-')
    //let data = gameData[gameID].split('-');
    let TURNS = data[3].slice(1,data[3].length-1).split(", ");
    //console.log(data)
    //(turn0, price1, colour2, seller3, buyer4)
    PRODUCE = 
    [<table className='Table'>
      <tr>
        <td></td>
        <td>Colour</td>
        <td>Price</td>
        <td>Seller</td>
        <td>Buyer</td>
      </tr>
      {data[0].split('), (').map(item => Produce_itemise(item,POV,TURNS.length,FOCUS_TURN))}
    </table>];

    //(turn0, price1, colour2, seller3, buyer4)
    WARES = 
    [<table className='Table'>
      <tr>
        <td></td>
        <td>Colour</td>
        <td>Price</td>
        <td>Seller</td>
        <td>Buyer</td>
      </tr>
      {data[1].split('), (').map(item => Produce_itemise(item,POV,TURNS.length,FOCUS_TURN))}
    </table>];

    //(turn, price, bundle of product, seller, buyer)
    AUCTION = 
    [<table className='Table'>
      <tr>
        <td></td>
        <td>Colour</td>
        <td>Price</td>
        <td>Seller</td>
        <td>Buyer</td>
      </tr>
      {data[2].split('), (').map(item => Auction_itemise(item,POV,TURNS.length,FOCUS_TURN))}
    </table>];

    /* HISTORY = data[3].map(item => <div>{item}</div>) */
    HISTORY = [];
    let scores = data[5].slice(1,data[5].length-1).split(', ')
    let names = data[6].slice(1,data[6].length-1).split(', ')
    for (let i=0;i<PLAYERS.length;i++){
      HISTORY.push(<div onClick={()=>setPOV(i)}>Player {i} ({names[i]}): {scores[i]}</div>)
    }
    HISTORY.push(<div>Turns [{TURNS.length}]</div>)
    for(let i = 0; i<TURNS.length; i++){
      HISTORY.push(
        <div className={`${POV == i%PLAYERS.length?"Highlight":""}`} onClick={()=>setTURN(i)}>Turn {i} [P{i%PLAYERS.length}]: <div className={`${TYPE == TURNS[i]?"Highlight2":""}`} onClick={()=>setTYPE(TURNS[i])}>{ACTION_KEY[TURNS[i]]}</div></div>
      )
    }

    VICTORY = <div>{data[4] == "P" ? "Pass Victory":data[4]}</div>
  }

  return (
    <div className="root">
      <div className="topbar">
        <input type="file" onChange={(e) => showFile(e)} />
        {gameData != "" && VICTORY}
        <button onClick={() => setGameID(gameID - 1)}>{"<"}</button>
        <div>Game {gameID}</div>
        <button onClick={() => setGameID(gameID + 1)}>{">"}</button>
      </div>
      <div className="bar1" onClick={()=>setTYPE(1)}>
        Produce
        {gameData != "" && PRODUCE}
      </div>
      <div className="bar2" onClick={()=>setTYPE(2)}>
        Wares
        {gameData != "" && WARES}
      </div>
      <div className="bar3" onClick={()=>setTYPE(6)}>
        Auction
        {gameData != "" && AUCTION}
      </div>
      <div className="bar4">
        History
        {gameData != "" && HISTORY}
      </div>
    </div>
  );
}

function Produce_itemise(item,POV,NUM_TURNS,FOCUS_TURN){
  if (item[0] === "["){item = item.slice(2,)}
  else if (item[item.length-1] === "]"){item = item.slice(0,item.length-1)}
  let data = item.split(', ') //(turn0, price1, colour2, seller3, buyer4)
  let P = (1-(data[0]/NUM_TURNS))*255;
  return(
    <tr className={`${FOCUS_TURN == data[0]?"Highlight2":""}`}>
      <td><div style={{background:`rgb(${P}, ${P}, ${P})`, display:"inline-block"}}>Turn</div> {data[0]}</td>
      <td style={{background:ALT_COLOURS[data[2]]}}></td>
      <td>${data[1]}</td>
      <td className={`${POV == data[3]?"Highlight":""}`}>{data[3]}</td>
      <td className={`${POV == data[4]?"Highlight":""}`}>{data[4]}</td>
    </tr>
  )
}

function Auction_itemise(item,POV,NUM_TURNS,FOCUS_TURN){
  if (item[0] === "["){item = item.slice(2,)}
  else if (item[item.length-1] === "]"){item = item.slice(0,item.length-1)}
  let first = item.split(", [");
  let left = first[0].split(", ");
  let middle = []
  let right = []
  if (first[1]){
    let second = first[1].split("], ");
    middle = second[0].split(", ");
    right = second[1].split(", ");
  }
  let P = (1-(left[0]/NUM_TURNS))*255;

  let COLOURS = [];
  for (let i=0;i<middle.length;i++){
    COLOURS.push(<div style={{background:ALT_COLOURS[i], display:"inline-flex"}}>{middle[i]}</div>)
  }

  
  /* for (let i=0;i<positions;i++){
    colour += 
  } */
  return(
    <tr className={`${FOCUS_TURN == left[0]?"Highlight2":""}`}>
      <td><div style={{background:`rgb(${P}, ${P}, ${P})`, display:"inline-block"}}>Turn</div> {left[0]} </td>
      <td>
        {COLOURS}
      </td>
      <td>${left[1]}</td>
      <td className={`${POV == right[0]?"Highlight":""}`}>{right[0]}</td>
      <td className={`${POV == right[1]?"Highlight":""}`}>{right[1]}</td>
    </tr>
  )
}

export default App;

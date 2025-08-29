import os
import yaml
import pandas as pd
import numpy as np
from datetime import datetime
from core.strategy_router import AdvancedStrategyRouter
from core.regime_detector import RegimeDetector
from core.risk_manager import PortfolioRiskManager
from utils.greeks import GreeksCalculator
from utils.iv_analysis import IVAnalyzer
from utils.logger import log

class DynamicBacktester:
    """Dynamic backtester integrating core components and saving detailed CSVs."""

    def __init__(self, config):
        self.cfg = config
        self.account_value = config['risk']['account_capital']
        self.router = AdvancedStrategyRouter(config)
        self.regime = RegimeDetector(config)
        self.riskmgr = PortfolioRiskManager(config)
        self.greeks = GreeksCalculator()
        self.iv_analyzer = IVAnalyzer()

    def run(self):
        instruments = [
            inst for inst, s in self.cfg['universe'].items() 
            if s.get('active', True)
        ]
        print("🚀 DYNAMIC BACKTESTER")
        print(f"Active instruments: {instruments}\n")

        for inst in instruments:
            df = self._load_data(inst)
            if df.empty:
                print(f"⚠️ No data for {inst}")
                continue
            df = df.tail(252)

            # Dynamic thresholds
            rsi_series = df['Close'].pct_change().rolling(14).apply(lambda x: np.mean(x>0)*100)
            vix_sim = df['Close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
            r_low, r_high = np.percentile(rsi_series.dropna(), [20,80])
            v_low, v_high = np.percentile(vix_sim.dropna(), [10,90])
            self.cfg['dynamic'] = {inst:{'rsi':(r_low,r_high),'vix':(v_low,v_high)}}
            print(f"{inst} thresholds → RSI {r_low:.1f}-{r_high:.1f}, VIX {v_low:.1f}-{v_high:.1f}")

            # Indicators
            df['sma20'] = df['Close'].rolling(20).mean()
            df['sma50'] = df['Close'].rolling(50).mean()
            df['atr'] = df['Close'].pct_change().rolling(14).std().iloc[:] * df['Close']

            trades = []  # ('E'/'X', date, strat, price, pnl_or_size)
            pos = None
            equity = self.account_value

            for idx in range(50, len(df)):
                date = df.index[idx]
                row = df.iloc[idx]
                vix = vix_sim.iloc[idx]
                live = {'vix':{'value':vix}}

                self.riskmgr.update_portfolio_state({} if pos is None else {'p':pos})

                if pos is None:
                    # try debit_spreads
                    sig, strat = self._try_debit_spreads(df, idx, live, inst)
                    if not sig:
                        sig, strat = self._try_iron_condor(df, idx, live, inst)
                    if not sig:
                        sig, strat = self._try_long_straddle(df, idx, live, inst)
                    if sig:
                        risk = equity * self.cfg['risk']['max_risk_per_trade_pct']
                        size = max(1,int(risk/df['atr'].iloc[idx]))
                        slip = np.random.normal(0,0.002)*row['Close']
                        pos = {
                            'entry_date':date,'entry':row['Close']+slip,
                            'size':size,'strat':strat
                        }
                        trades.append(('E',date,strat,pos['entry'],size))
                        print(f"📈 {inst} Entry {strat} @₹{pos['entry']:.2f} x{size}")
                else:
                    held=(date-pos['entry_date']).days
                    change=(row['Close']-pos['entry'])/pos['entry']
                    if held>=5 or abs(change)>=0.05:
                        pnl=change*pos['size']*pos['entry']
                        trades.append(('X',date,pos['strat'],row['Close'],pnl))
                        print(f"📉 {inst} Exit {pos['strat']} @₹{row['Close']:.2f} P&L=₹{pnl:.0f}")
                        equity+=pnl
                        pos=None

            # Build CSV
            rows=[]
            for t in trades:
                if t[0]=='X':
                    exit_date, strat, exit_price, pnl = t[1], t[2], t[3], t[4]
                    # find matching entry
                    entries=[e for e in trades if e[0]=='E' and e[2]==strat and e[1]<exit_date]
                    if not entries: continue
                    ed=entries[-1]
                    rows.append({
                        'entry_date':ed[1],'entry_price':ed[3],
                        'direction':ed[2],'exit_date':exit_date,
                        'exit_price':exit_price,'pnl':pnl
                    })
            df_csv=pd.DataFrame(rows,columns=[
                'entry_date','entry_price','direction',
                'exit_date','exit_price','pnl'
            ])
            out=f"results/backtest_{inst}_trades.csv"
            df_csv.to_csv(out,index=False)
            print(f"💾 Saved {len(df_csv)} trades for {inst} → {out}\n")

    def _try_debit_spreads(self, df, idx, live, inst):
        r_low,r_high=self.cfg['dynamic'][inst]['rsi']
        v_low,v_high=self.cfg['dynamic'][inst]['vix']
        rsi=100*np.mean(df['Close'].pct_change().tail(14)>0)
        if not (r_low<=rsi<=r_high): return None,None
        if live['vix']['value']>v_high: return None,None
        return {'direction':'bullish','confidence':50},'debit_spreads'

    def _try_iron_condor(self, df, idx, live, inst):
        row=df.iloc[idx]
        rng=(df['High'].tail(10).max()-df['Low'].tail(10).min())/row['Close']
        if rng>0.12: return None,None
        return {'direction':'neutral','confidence':50},'iron_condor'

    def _try_long_straddle(self, df, idx, live, inst):
        row=df.iloc[idx]
        rng=(df['High'].tail(5).max()-df['Low'].tail(5).min())/row['Close']
        if rng>0.08: return None,None
        if live['vix']['value']>25: return None,None
        return {'direction':'long_vol','confidence':50},'long_straddle'

    def _load_data(self, inst):
        for p in [f"data/{inst}_historical.csv",f"{inst}.csv"]:
            if os.path.exists(p):
                return pd.read_csv(p,parse_dates=[0],index_col=0)
        return pd.DataFrame()

if __name__=="__main__":
    config=yaml.safe_load(open('config.yaml'))
    DynamicBacktester(config).run()

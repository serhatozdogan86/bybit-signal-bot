# Retail'de En Popüler Stratejiler — Aday Araştırma Raporu (Denetim şeridi; kod değişikliği yok)

**Method note:** tradingview.com is egress-blocked from this environment, so popularity figures come from secondary sources (pineindicators, quantum-algo, daviddtech, traderslist mirrors). All mechanisms below are from public/open-source documentation only.

## Candidate-by-candidate

### 1. SuperTrend (ATR band flip)
- **Source/popularity:** Consistently top-3 in every "most used TradingView indicator" list ([pineindicators](https://pineindicators.com/top-tradingview-scripts-2025/), [tradenation](https://tradenation.com/articles/tradingview-indicators/)); ported everywhere (MT4/5, freqtrade).
- **Mechanism (public):** Basic bands = (H+L)/2 ± m·ATR(n) (default m=3, n=10), with a ratchet: the band only tightens, never loosens, until price closes through it; flip = signal. It is a stop-and-reverse ATR trailing stop.
- **Family:** time-series trend following with volatility-adaptive trail → **overlaps S1 (EMA200+momentum) and partially the champion breakout**. Same family as UT Bot, Chandelier Exit, Parabolic SAR.
- **Evidence:** Mixed. [QuantifiedStrategies](https://www.quantifiedstrategies.com/supertrend-indicator/) finds value on long histories with rules; [LiberatedStockTrader (4,052 trades)](https://www.liberatedstocktrader.com/supertrend-indicator/) finds 42% win rate and net-unprofitable on plain daily OHLC; [Quant4Free](https://quant4free.com/analysis/supertrend/): "regime decides more than the indicator."
- **Measurement fit:** good — flip level gives a defined stop, discrete trades.
- **Verdict: REDUNDANT** (S1 family relative with different clothing). Only novel piece is the ratcheting ATR trail as an *exit policy* — see shortlist.

### 2. UT Bot Alerts (QuantNomad)
- **Popularity:** ~1.1M views, 35,500+ boosts, author >100K followers ([quantum-algo guide](https://www.quantum-algo.com/blog/guides/ut-bot-alerts-complete-guide/)).
- **Mechanism:** ATR trailing stop with sensitivity "key value" a: trail = close ∓ a·ATR(period), ratcheted; buy when close crosses above trail, sell below ([FMZ writeup](https://medium.com/@FMZQuant/ut-bot-indicator-based-atr-trailing-stop-strategy-5660449d5431)). Literally SuperTrend with different defaults.
- **Evidence:** only anecdotal blog backtests (60% WR over 3 months EUR/USD — tiny samples); no rigorous independent test found.
- **Verdict: REDUNDANT** — same family as #1; its popularity is packaging (alerts), not mechanism.

### 3. Squeeze Momentum [LazyBear] / TTM Squeeze (John Carter)
- **Popularity:** ~76,000 boosts, routinely cited as the #1 community script ([daviddtech](https://daviddtech.medium.com/the-best-indicator-on-tradingview-squeeze-momentum-indicator-strategy-lazybear-8595777423d0), [pickmytrade](https://blog.pickmytrade.trade/squeeze-momentum-strategy/)).
- **Mechanism (public):** Squeeze ON when Bollinger Bands(20, 2σ) sit entirely inside Keltner Channels(20, 1.5·ATR) → low-volatility compression. Squeeze "fires" when BB re-exit KC; direction taken from a linear-regression momentum histogram of price vs. midline ([StockCharts ChartSchool](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/ttm-squeeze)).
- **Family:** **volatility-compression breakout** — cousin of S2 Donchian breakout and champion, but the *compression precondition* is a genuinely different trigger: it trades expansion out of quiet, not strength continuation.
- **Evidence:** [Volatility Box](https://volatilitybox.com/research/ttm-squeeze-indicator/) reports S&P500 squeeze-fires preceding ≥2× average-range moves within 5 bars ~68% of the time (direction not guaranteed!); crypto ports report best behavior on 4h ([Bitduke strategy](https://www.tradingview.com/script/5tuGpzpd-Squeeze-Momentum-Strategy-based-on-Indicator-LazyBear-Bitduke/), ~12% DD claim, unaudited). Academic relative: range contraction → expansion is Toby Crabel's documented effect ([Traders Log overview](https://www.traderslog.com/volatility-breakout-systems)); volatility clustering (GARCH) is one of the most robust stylized facts in finance — but note it predicts *magnitude*, not *direction*; the directional edge remains unproven.
- **Measurement fit:** excellent — compression range gives a natural stop (opposite side of the squeeze range), discrete clustered trades, works on 4H.
- **Verdict: WORTH PRE-REGISTERING** (top pick). Must pre-register exact BB/KC parameters and direction rule to avoid p-hacking (Kural 4/5).

### 4. Opening/Session Range Breakout with relative-volume gate (Zarattini–Aziz)
- **Popularity:** ORB is a retail staple; the academic papers went viral in retail circles.
- **Mechanism:** Buy/sell breakout of the first N-minute range of the session; stop at range's other side. Key finding of the 2024 paper: **plain ORB was weak — selecting instruments with unusually high opening relative volume did almost all the work** ([SSRN 4729284](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284), Sharpe 2.4 on 7,000 US stocks 2016-23; earlier QQQ paper [SSRN 4416622](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416622); skeptical read: [CXO Advisory](https://www.cxoadvisory.com/technical-trading/day-trading-with-an-opening-range-breakout-strategy/) — simplified execution, no slippage, parameter search behind headline numbers).
- **Family:** breakout (S2 cousin) × calendar window (S9 cousin) × **relative-volume participation filter = NEW element** not in the roster.
- **Crypto adaptation:** no open bell, but real session anchors exist (00:00 UTC daily candle, US equity open 13:30/14:30 UTC, CME futures open) and the bot already has evidence calendar windows matter (S9). The transferable, genuinely new mechanism is the *unusual-volume gate* on breakouts.
- **Measurement fit:** excellent — defined range stop, naturally clustered by day.
- **Verdict: WORTH PRE-REGISTERING** (as "session-anchored breakout gated by relative volume", not as literal ORB).

### 5. Machine Learning: Lorentzian Classification (jdehorty)
- **Popularity:** TradingView "Most Valuable" Pine publication of 2023, Editor's Pick, one of the most-boosted scripts ever ([script page](https://www.tradingview.com/script/WhBzgfDu-Machine-Learning-Lorentzian-Classification/)).
- **Mechanism (public, open source):** approximate k-nearest-neighbors classifier using Lorentzian distance log(1+|xᵢ−yᵢ|) over features (RSI, WT, CCI, ADX at various params); each historical bar labeled by 4-bars-ahead price direction; prediction = sum of neighbor labels; filters (volatility, regime, EMA/SMA, kernel regression estimate) gate signals.
- **Family:** nonparametric pattern matcher over *oscillator features* — no single roster family; effectively automated curve-fitting.
- **Evidence:** author himself says the built-in "Trade Stats" is "for calibration, not a substitute for rigorous backtesting"; claims no repaint after bar close; community backtests wildly inconsistent ([TradeSearcher, 96 backtests](https://tradesearcher.ai/strategies/2019-lorentzian-classification-strategy); [MQL5 forum port discussion](https://www.mql5.com/en/forum/442465)). Label definition (looks 4 bars ahead during training on the same series it trades) makes in-sample results near-meaningless.
- **Measurement fit:** poor — no natural stop, huge parameter surface, unfalsifiable as pre-registered hypothesis.
- **Verdict: TRAP.** At most a curiosity benchmark; violates the repo's pre-registration spirit.

### 6. VuManChu Cipher B / WaveTrend oscillator
- **Popularity:** among the most-used free crypto indicators; free clone of the paid Market Cipher ($499+ tier product); defaults tuned for BTCUSDT ([Gainium explainer](https://gainium.io/blog/vumanchu-cipher-b-indicator-explained), [tlap.io](https://tlap.io/en/vumanchu-indicator-basics)).
- **Mechanism (public):** WaveTrend: esa=EMA(hlc3,n1); d=EMA(|hlc3−esa|,n1); ci=(hlc3−esa)/(0.015·d); wt1=EMA(ci,n2); wt2=SMA(wt1,4); signals = wt cross in OB/OS zones + RSI/MFI + divergence dots.
- **Family:** oscillator overbought/oversold **mean reversion + divergence reversal → dead-family relative of S3 (−158R) and S6 (−84R)**.
- **Evidence:** no rigorous independent evidence; TradeSearcher community backtests mixed ([97 backtests](https://tradesearcher.ai/strategies/1622-vumanchu-cipher-b-divergences-strategy)); RSI-style mean reversion specifically shown not to work on BTC ([QuantifiedStrategies BTC RSI test](https://www.quantifiedstrategies.com/bitcoin-rsi-trading-strategy/) — "RSI works on BTC as momentum, not mean reversion").
- **Verdict: TRAP (dead family).**

### 7. QQE Mod
- **Popularity:** top-10 lists everywhere; a favorite in freqtrade strategies too ([ForexBee](https://forexbee.co/qqe-indicator/), [TakeProfit port](https://takeprofit.com/indicator/qqe-mod-indicator-mihkel00-concept-port-12)).
- **Mechanism:** Wilder-smoothed RSI(5-14) with an ATR-of-RSI trailing band (factor 4.236); cross of smoothed RSI through its own trailing band = signal.
- **Family:** momentum oscillator with trailing logic — hybrid of S1 momentum and oscillator reversal; nothing mechanistically new.
- **Evidence:** none independent beyond content-farm backtests.
- **Verdict: REDUNDANT.**

### 8. ICT / Smart Money Concepts (order blocks, fair value gaps, liquidity sweeps) — incl. LuxAlgo's SMC toolkit
- **Popularity:** the dominant retail narrative of 2022-2026; LuxAlgo (one of the largest paid TradingView vendors, Trustpilot 4.5/1,600 reviews) ships a free SMC suite ([LuxAlgo FVG library](https://www.luxalgo.com/library/concept/fair-value-gap/)).
- **Mechanism (public parts):** order block = last opposing candle before an impulsive move (support/resistance re-labeled); FVG = 3-candle gap where candle1.high < candle3.low (imbalance), traded on the expectation price "rebalances" into it; liquidity sweep = stop-hunt beyond swing high/low then reversal.
- **Family:** **liquidity-sweep reversal = literally dead S6 (−84R); "spring" logic = S7 already covers the tradable core.** FVG-fill is gap-fill mean reversion.
- **Evidence:** inherently subjective ("two traders mark different order blocks" — [backtrex](https://backtrex.com/en/blog/what-is-smart-money-concepts-trading)); the viral "FVG fills 70% of the time" stat ([Medium, 2,600 trades](https://medium.com/@QuantumAlgo/i-backtested-2-600-trades-using-smart-money-concepts-heres-what-actually-works-bb3c671098c6)) is a base-rate illusion — most gaps fill mechanically in any random-walk series; the institutional-order-flow story is described by skeptics as "a marketing narrative."
- **Verdict: TRAP (dead-family + unfalsifiable).** S6's grave is already the empirical answer.

### 9. NostalgiaForInfinity (freqtrade flagship)
- **Popularity:** ~3.3k stars / 741 forks, by far the most used freqtrade community strategy ([github.com/iterativv/NostalgiaForInfinity](https://github.com/iterativv/NostalgiaForInfinity)).
- **Mechanism:** 5m timeframe, 40-80 pair portfolio, hundreds of tagged entry conditions (mostly dip-buying/mean-reversion with multi-timeframe protections), "derisking" position management that scales out instead of hard stops, continuous re-tuning by maintainer (version churn is constant).
- **Family:** portfolio mean-reversion dip buyer with soft stops → **dead-family relative of S3**, plus DCA-ish position management.
- **Evidence:** official backtests only in commit comments; live-tracking sites like [strat.ninja](https://www.strat.ninja/overview.php?strategy=NostalgiaForInfinityNext) show mediocre/volatile results; the strategy is re-fit so often that any long-horizon claim is unmeasurable — a moving target is untestable by our ≥50-cluster CI standard.
- **Measurement fit:** terrible for this bot — needs 5m, many simultaneous pairs, no fixed per-trade R.
- **Verdict: TRAP for our framework** (also incompatible with single-pair single-leg design).

### 10. Grid bots (Pionex) / DCA bots (3Commas) / MQL5 martingale-grid EAs
- **Popularity:** Pionex's grid bot is its flagship ([docs](https://support.pionex.com/hc/en-us/articles/45085712163225-Grid-Trading-Bot)); 3Commas DCA bot with safety orders is the standard retail crypto bot ([3Commas](https://developers.3commas.io/dca-bot/)); on MQL5 the best-seller in history, Quantum Emperor (5,000+ sales, ~$5M revenue, 4.87★), is per independent review "a cleverly disguised martingale-grid system" that took a **70% drawdown in June 2024** ([review](https://newyorkcityservers.com/blog/quantum-emperor-review)); Gold Reaper similar ([review context](https://www.mql5.com/en/blogs/post/758268)).
- **Mechanism:** grid = ladder of buy-low/sell-high limit orders in a band (short volatility, long mean reversion); DCA/martingale = averaging down with growing size, take-profit on reversion; no per-trade stop.
- **Why they look great until they blow up:** high win rate + tiny wins + unbounded tail loss. The equity curve smoothness is the *product being sold*; the risk is hidden in open drawdown. Academic treatment confirms: "range-bound conditions → gains; markets trending too long in one direction → large losses; the most profitable simulations are unstable and lead to ruin" ([Bi-Directional Grid Constrained Stochastic Processes](https://www.researchgate.net/publication/349836417_Application_of_Bi-Directional_Grid_Constrained_Stochastic_Processes_to_Algorithmic_Trading); [failure-mode blog on MQL5 itself](https://www.mql5.com/en/blogs/post/768549)).
- **Risk-bounded R-multiple variant?** Technically expressible: a single-entry range-fade with hard stop below the range = "one rung of the grid, honestly priced." But that *is* mean reversion with a stop — **exactly what S3 was, and S3 died at −158R.** The grid's apparent profitability comes precisely from *not* taking the stop.
- **Verdict: TRAP (and dead-family once made honest).** Its only legitimate lesson: the roster's funding-carry S4 is the honest way to be short volatility.

### 11. Ichimoku Kinko Hyo systems
- **Popularity:** perennial top-10; huge follower base.
- **Mechanism:** Tenkan(9)/Kijun(26) midpoint crosses, cloud (Senkou A/B displaced 26 forward), Chikou confirmation — a multi-condition trend filter of price-midpoint averages.
- **Family:** trend following → **overlaps S1/S2**.
- **Evidence:** violently mixed — [QuantifiedStrategies](https://www.quantifiedstrategies.com/ichimoku-strategy/) modest positive (PF 1.1-1.47); [LiberatedStockTrader, 15,024 trades](https://www.liberatedstocktrader.com/ichimoku-cloud/) found a 10% win rate, underperforming buy-and-hold 90% of the time on DJ-30; [Coinquant BTC 8y](https://www.coinquant.ai/blog/ichimoku-cloud-strategy-on-bitcoin-8-years-of-backtest-results) PF 1.95 on 12 trades (sample far too small).
- **Verdict: REDUNDANT** — nothing here S1+S2 don't already measure.

### 12. Parabolic SAR / Chandelier Exit (everget's port is a TradingView staple)
- **Mechanism:** PSAR = accelerating trailing stop-and-reverse (AF 0.02→0.2); Chandelier = highest(high,22) − 3·ATR(22) trailing exit (Chuck LeBeau, 1992).
- **Family:** ATR/trailing exits — same family as #1/#2.
- **Evidence:** PSAR standalone is poor on OHLC charts (10-30% WR; [StockChartPro 20k trades](https://www.stockchartpro.com/parabolic-sar/), [QuantifiedStrategies](https://www.quantifiedstrategies.com/parabolic-sar-trading-strategy/)); as an *exit overlay* on trend entries, trailing ATR stops are consistent with the trend-following literature (let winners run, cut losers — the mechanism behind Moskowitz-Ooi-Pedersen time-series momentum payoff shape, which crypto studies confirm transfers: [TSM in crypto](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf), [Dynamic TSM of cryptocurrencies](https://www.sciencedirect.com/science/article/abs/pii/S1062940821000590)).
- **Verdict: not an entry candidate; PRE-REGISTER AS EXIT-POLICY EXPERIMENT** for a future v2 champion design (fixed-R exit vs ATR-ratchet trail, measured on the same entries). Strategies are frozen (Kural 1) — this is a design note for the not-yet-designed v2, not a change request.

## Ranked shortlist — genuinely worth pre-registering (docs/ideas.md style, FUTURE data only)

1. **Volatility-compression-gated breakout (TTM/LazyBear squeeze family).** New trigger vs S2 (compression precondition rather than raw channel break); natural stop = far side of compression range; strongest academic cousin (volatility clustering + Crabel range contraction); 4H-friendly; clusters cleanly. Pre-register: BB(20,2) inside KC(20,1.5·ATR) ≥ N bars, entry on close beyond squeeze range, direction by momentum histogram sign, stop at opposite range edge.
2. **Session-anchored breakout gated by unusual relative volume (Zarattini adaptation).** The relative-volume participation gate is the one element with real peer-reviewed support and absent from the roster; combines naturally with the bot's proven calendar sensitivity (S9). Pre-register anchor (e.g. 00:00 UTC or US-open), range window, rel-vol threshold defined on prior data only.
3. **ATR-ratchet trailing exit vs fixed-R exit (Chandelier/SuperTrend mechanism as exit policy, not entry).** Cheapest genuine insight from the entire retail canon; test on a pre-registered future candidate, never on frozen engines.
4. *(distant 4th)* **SuperTrend-flip as a regime filter overlay** for existing family measurement — only if v2 champion design wants a volatility-adaptive regime input; as a standalone entry it is redundant with S1.

Everything else surveyed is redundant (UT Bot, QQE, Ichimoku, PSAR-entry), a dead-family relative (Cipher B/WaveTrend reversal, SMC liquidity sweeps ≈ S6, FVG-fill/grid/DCA/NFI ≈ S3), or unfalsifiable (Lorentzian ML, discretionary ICT).

## Why "most popular" ≠ "most profitable"

- **The marketplace selects for equity-curve aesthetics, not expectancy.** MQL5's all-time best seller is a disguised martingale that dropped 70% in one month *after* accumulating 5,000 sales; grid/DCA products monetize the smoothness that hidden tail risk buys ([Quantum Emperor review](https://newyorkcityservers.com/blog/quantum-emperor-review), [martingale failure analysis](https://www.mql5.com/en/blogs/post/768549)).
- **Survivorship & churn:** NFI is perpetually re-fit; failed versions vanish into commit history; strat.ninja live tracking rarely matches marketing.
- **Repainting:** per TradersPost "more than 95% of indicators exhibit some form of repainting" (esp. `security()` higher-timeframe calls and intrabar signals); "every paid indicator advertises itself as non-repaint" — the claim itself is a marketing genre. LuxAlgo has user complaints of repainting and of backtests losing despite 60% win rates ([TradersPost explainer](https://blog.traderspost.io/article/what-is-repainting-in-tradingview-and-how-do-i-find-it-and-avoid-it), [QuantVPS LuxAlgo review](https://www.quantvps.com/blog/luxalgo-review)). Lorentzian explicitly defends itself against repaint accusations, which tells you how endemic the accusation is. Any adopted rule must be evaluated bar-close-only, as the bot already does.
- **Popularity is driven by signal legibility** (dots, arrows, alerts — UT Bot's entire value-add) **and narrative appeal** (ICT's "smart money" story), neither of which is a return driver; the academic record supports only two of the underlying mechanisms surveyed (trend/TSM payoffs, volatility clustering/compression-expansion), both of which the roster already partially holds.
- **Aggregated community backtests (TradeSearcher etc.) are naive:** no fees/funding, cherry-picked windows, per-strategy parameter search — the same look-ahead the repo's Kural 4/5 exist to prevent.

**Roster cross-check summary:** trend/breakout families (S1/S2/champion) are heavily validated by retail popularity *and* academia; the two dead engines (S3 mean reversion, S6 liquidity sweep) are precisely the two most heavily *marketed* retail families (oscillator reversal, SMC) — the bot's own graveyard independently replicates the skeptical literature. No search result gave reason to revive either.
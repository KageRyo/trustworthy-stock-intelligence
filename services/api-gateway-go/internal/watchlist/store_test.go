package watchlist

import "testing"

func TestResolveTickerMapsNumericAutoToTWSE(t *testing.T) {
	resolved, err := ResolveTicker("2330", MarketAuto)
	if err != nil {
		t.Fatalf("ResolveTicker returned error: %v", err)
	}

	if resolved.Ticker != "2330" || resolved.QuerySymbol != "2330.TW" || resolved.Market != "twse" {
		t.Fatalf("unexpected resolved ticker: %+v", resolved)
	}
}

func TestResolveTickerMapsTaiwanAlphanumericAutoToTWSE(t *testing.T) {
	testCases := []string{"00981A", "02001L"}
	for _, ticker := range testCases {
		resolved, err := ResolveTicker(ticker, MarketAuto)
		if err != nil {
			t.Fatalf("ResolveTicker(%q) returned error: %v", ticker, err)
		}
		if resolved.Ticker != ticker || resolved.QuerySymbol != ticker+".TW" || resolved.Market != "twse" {
			t.Fatalf("unexpected resolved ticker for %s: %+v", ticker, resolved)
		}
	}
}

func TestResolveTickerMapsTPEXCode(t *testing.T) {
	resolved, err := ResolveTicker("6488", MarketTPEX)
	if err != nil {
		t.Fatalf("ResolveTicker returned error: %v", err)
	}

	if resolved.Ticker != "6488" || resolved.QuerySymbol != "6488.TWO" || resolved.Market != "tpex" {
		t.Fatalf("unexpected resolved ticker: %+v", resolved)
	}
}

func TestResolveTickerMapsTaiwanAlphanumericTPEXCode(t *testing.T) {
	resolved, err := ResolveTicker("02001L", MarketTPEX)
	if err != nil {
		t.Fatalf("ResolveTicker returned error: %v", err)
	}

	if resolved.Ticker != "02001L" || resolved.QuerySymbol != "02001L.TWO" || resolved.Market != "tpex" {
		t.Fatalf("unexpected resolved ticker: %+v", resolved)
	}
}

func TestResolveTickerMapsEmergingCode(t *testing.T) {
	resolved, err := ResolveTicker("5240", MarketESB)
	if err != nil {
		t.Fatalf("ResolveTicker returned error: %v", err)
	}

	if resolved.Ticker != "5240" || resolved.QuerySymbol != "5240.EMERGING" || resolved.Market != "emerging" {
		t.Fatalf("unexpected resolved ticker: %+v", resolved)
	}
}

func TestResolveTickerMapsEmergingSuffixInAutoMode(t *testing.T) {
	resolved, err := ResolveTicker("5240.emerging", MarketAuto)
	if err != nil {
		t.Fatalf("ResolveTicker returned error: %v", err)
	}

	if resolved.Ticker != "5240" || resolved.QuerySymbol != "5240.EMERGING" || resolved.Market != "emerging" {
		t.Fatalf("unexpected resolved ticker: %+v", resolved)
	}
}

func TestShouldMergeStaleUSTickerAliasForTaiwanMarkets(t *testing.T) {
	testCases := []ResolvedTicker{
		{Ticker: "00981A", QuerySymbol: "00981A.TW", Market: "twse"},
		{Ticker: "02001L", QuerySymbol: "02001L.TWO", Market: "tpex"},
		{Ticker: "5240", QuerySymbol: "5240.EMERGING", Market: "emerging"},
	}
	for _, ticker := range testCases {
		if !shouldMergeStaleUSTickerAlias(ticker) {
			t.Fatalf("expected stale US alias merge for %+v", ticker)
		}
	}
}

func TestShouldNotMergeStaleUSTickerAliasForUSMarkets(t *testing.T) {
	testCases := []ResolvedTicker{
		{Ticker: "AAPL", QuerySymbol: "AAPL", Market: "us"},
		{Ticker: "00981A", QuerySymbol: "00981A", Market: "us"},
	}
	for _, ticker := range testCases {
		if shouldMergeStaleUSTickerAlias(ticker) {
			t.Fatalf("did not expect stale US alias merge for %+v", ticker)
		}
	}
}

func TestResolveTickerRejectsInvalidTWSECode(t *testing.T) {
	_, err := ResolveTicker("NVDA", MarketTWSE)

	if err == nil {
		t.Fatal("expected invalid Taiwan code error")
	}
}

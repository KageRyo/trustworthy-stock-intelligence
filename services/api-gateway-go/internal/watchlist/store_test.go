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

func TestResolveTickerMapsTPEXCode(t *testing.T) {
	resolved, err := ResolveTicker("6488", MarketTPEX)
	if err != nil {
		t.Fatalf("ResolveTicker returned error: %v", err)
	}

	if resolved.Ticker != "6488" || resolved.QuerySymbol != "6488.TWO" || resolved.Market != "tpex" {
		t.Fatalf("unexpected resolved ticker: %+v", resolved)
	}
}

func TestResolveTickerRejectsInvalidTWSECode(t *testing.T) {
	_, err := ResolveTicker("NVDA", MarketTWSE)

	if err == nil {
		t.Fatal("expected invalid Taiwan code error")
	}
}

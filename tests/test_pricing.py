from wind_trader.pricing import calc_limit_price, infer_limit_pct, infer_tick_size


def test_infer_limit_pct():
    assert infer_limit_pct("600000.SH") == 0.10
    assert infer_limit_pct("300750.SZ") == 0.20
    assert infer_limit_pct("688001.SH") == 0.20
    assert infer_limit_pct("430001.BJ") == 0.20
    assert infer_limit_pct("600600.SH", "ST海") == 0.05


def test_infer_tick_size():
    assert infer_tick_size("600000.SH") == 0.01
    assert infer_tick_size("430001.BJ") == 0.001


def test_calc_limit_price_buy_sell():
    assert calc_limit_price(10.0, "Buy", 0.10, 0.01) == 11.0
    assert calc_limit_price(10.0, "Sell", 0.10, 0.01) == 9.0
    assert calc_limit_price(10.0, "Buy", 0.20, 0.001) == 12.0

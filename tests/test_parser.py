from pybhav.parser import parse


def test_parse_returns_dataframe():
    csv = b" SYMBOL , OPEN , CLOSE \nRELIANCE,2900,2950\n"
    df = parse(csv)
    assert list(df.columns) == ["SYMBOL", "OPEN", "CLOSE"]
    assert df.iloc[0]["SYMBOL"] == "RELIANCE"


def test_parse_strips_column_whitespace():
    csv = b"  SYMBOL  ,  CLOSE  \nINFY,1800\n"
    df = parse(csv)
    assert "SYMBOL" in df.columns
    assert "CLOSE" in df.columns

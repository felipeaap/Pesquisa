from tqdm import tqdm

POSITIONS = {
    "pubmed":    0,
    "scielo":    1,
    "openalex":  2,
    "arxiv":     3,
}

def make_bar(source: str, desc: str, **kwargs) -> tqdm:
    return tqdm(
        desc=desc,
        position=POSITIONS.get(source, 0),
        leave=True,
        dynamic_ncols=True,
        **kwargs
    )
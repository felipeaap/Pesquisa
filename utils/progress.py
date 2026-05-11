from tqdm import tqdm
from contextlib import suppress

POSITIONS = {
    "pubmed":    0,
    "scielo":    1,
    "openalex":  2,
    "arxiv":     3,
}


class ManagedTqdm(tqdm):
    def __exit__(self, exc_type, exc_val, exc_tb):
        with suppress(Exception):
            self.clear()

        with suppress(Exception):
            self.close()

        return super().__exit__(exc_type, exc_val, exc_tb)


def make_bar(source: str, desc: str, unit:str = "art", **kwargs) -> tqdm:
    return ManagedTqdm(
        desc=desc,
        position=POSITIONS[source],
        leave=False,
        dynamic_ncols=True,
        unit=unit,
        smoothing=0.1,
        colour="green",
        bar_format=(
            "{desc:<40} "
            "{n_fmt:>4}/{total_fmt:<4} "
            "[{elapsed}<{remaining}, {rate_fmt}]"
        ),
        **kwargs
    )
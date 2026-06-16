from pathlib import Path

import yaml

from research_agent.labels import ALL_CASES


def test_default_queries_target_all_balance_cases():
    config = yaml.safe_load(Path("config/queries.yaml").read_text(encoding="utf-8"))
    covered_cases = set()

    for query_config in config["queries"]:
        target_cases = set(query_config.get("target_cases", []))
        assert target_cases, f"{query_config['name']} has no target_cases"
        assert target_cases <= set(ALL_CASES), query_config["name"]
        covered_cases.update(target_cases)

    assert covered_cases == set(ALL_CASES)


def test_hard_real_disaster_figurative_image_bucket_has_dedicated_queries():
    config = yaml.safe_load(Path("config/queries.yaml").read_text(encoding="utf-8"))
    hard_case = "figurative_text__figurative_image__real_disaster"
    dedicated_queries = [
        query_config
        for query_config in config["queries"]
        if query_config.get("target_cases") == [hard_case]
    ]

    assert len(dedicated_queries) >= 4

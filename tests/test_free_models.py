from radar.providers import rank_free

CATALOGUE = {
    "data": [
        {"id": "paid/one", "context_length": 900000, "supported_parameters": ["response_format"]},
        {
            "id": "small/one:free",
            "context_length": 8000,
            "supported_parameters": ["response_format", "structured_outputs"],
        },
        {
            "id": "big/one:free",
            "context_length": 262144,
            "supported_parameters": ["response_format", "structured_outputs"],
        },
        {"id": "plain/one:free", "context_length": 500000, "supported_parameters": ["temperature"]},
        {
            "id": "mid/one:free",
            "context_length": 128000,
            "supported_parameters": ["response_format"],
        },
    ]
}


class TestRanking:
    def test_only_free_models_are_considered(self):
        assert all(m.model_id.endswith(":free") for m in rank_free(CATALOGUE))

    def test_models_that_can_be_forced_to_json_come_first(self):
        """A model that guarantees JSON is worth more here than a longer context."""
        ranked = rank_free(CATALOGUE)
        assert ranked[0].model_id == "big/one:free"
        assert ranked[-1].model_id == "plain/one:free"

    def test_structured_output_support_outranks_plain_json_mode(self):
        ranked = [m.model_id for m in rank_free(CATALOGUE)]
        assert ranked.index("small/one:free") < ranked.index("mid/one:free")

    def test_context_length_breaks_ties(self):
        ranked = [m.model_id for m in rank_free(CATALOGUE)]
        assert ranked.index("big/one:free") < ranked.index("small/one:free")

    def test_whether_json_can_be_forced_is_recorded_per_model(self):
        by_id = {m.model_id: m for m in rank_free(CATALOGUE)}
        assert by_id["big/one:free"].supports_json is True
        assert by_id["plain/one:free"].supports_json is False

    def test_the_list_is_capped(self):
        assert len(rank_free(CATALOGUE, limit=2)) == 2

    def test_a_catalogue_with_no_free_models_is_empty_not_an_error(self):
        assert rank_free({"data": [{"id": "paid/only", "supported_parameters": []}]}) == []

    def test_a_malformed_catalogue_is_empty_not_a_crash(self):
        assert rank_free({}) == []
        assert rank_free({"data": "nonsense"}) == []

from src.assessment.footwork_assessment import FootworkAssessmentBuilder


def test_footwork_builder_allocates_validator_safe_assessment_id():
    builder = FootworkAssessmentBuilder(
        config_version="test-config",
        calibration_snapshot={},
    )

    assert isinstance(builder.assessment_id, str)
    assert builder.assessment_id.startswith("fa_")
    assert len(builder.assessment_id) > 3

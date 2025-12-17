"""Unit tests for VisualPlan and related models."""

import pytest
from pydantic import ValidationError

from src.models import (
    VisualAsset,
    VisualAssetOrigin,
    VisualOpportunity,
    VisualPlan,
    VisualPlacement,
)


class TestVisualAsset:
    """Tests for VisualAsset model."""

    def test_create_minimal_asset(self):
        """Test creating a visual asset with required fields."""
        asset = VisualAsset(
            id="asset-1",
            filename="image.png",
            media_type="image/png",
        )
        assert asset.id == "asset-1"
        assert asset.filename == "image.png"
        assert asset.media_type == "image/png"
        assert asset.origin == VisualAssetOrigin.client_provided

    def test_create_asset_with_all_fields(self):
        """Test creating a visual asset with all optional fields."""
        asset = VisualAsset(
            id="asset-2",
            filename="diagram.svg",
            media_type="image/svg+xml",
            origin=VisualAssetOrigin.generated,
            source_url="https://example.com/diagram.svg",
            storage_key="uploads/diagram.svg",
            width=800,
            height=600,
            alt_text="Architecture diagram",
            tags=["architecture", "diagram"],
        )
        assert asset.origin == VisualAssetOrigin.generated
        assert asset.source_url == "https://example.com/diagram.svg"
        assert asset.width == 800
        assert asset.height == 600
        assert asset.alt_text == "Architecture diagram"
        assert "architecture" in asset.tags

    def test_asset_invalid_dimensions(self):
        """Test that invalid dimensions raise ValidationError."""
        with pytest.raises(ValidationError):
            VisualAsset(
                id="asset-3",
                filename="image.png",
                media_type="image/png",
                width=0,  # Must be >= 1
            )

    def test_asset_extra_fields_forbidden(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError) as exc_info:
            VisualAsset(
                id="asset-4",
                filename="image.png",
                media_type="image/png",
                unknown_field="value",
            )
        assert "extra" in str(exc_info.value).lower()

    def test_asset_origin_enum_values(self):
        """Test all VisualAssetOrigin enum values."""
        origins = [
            VisualAssetOrigin.client_provided,
            VisualAssetOrigin.user_uploaded,
            VisualAssetOrigin.generated,
            VisualAssetOrigin.external_link,
        ]
        for origin in origins:
            asset = VisualAsset(
                id="test",
                filename="test.png",
                media_type="image/png",
                origin=origin,
            )
            assert asset.origin == origin


class TestVisualOpportunity:
    """Tests for VisualOpportunity model."""

    def test_create_minimal_opportunity(self):
        """Test creating an opportunity with required fields."""
        opportunity = VisualOpportunity(
            id="opp-1",
            chapter_index=1,
            visual_type="diagram",
            title="System Architecture",
            prompt="A diagram showing the system architecture",
            caption="Figure 1: System Architecture Overview",
        )
        assert opportunity.id == "opp-1"
        assert opportunity.chapter_index == 1
        assert opportunity.visual_type == "diagram"
        assert opportunity.placement == VisualPlacement.after_heading

    def test_create_opportunity_with_all_fields(self):
        """Test creating an opportunity with all optional fields."""
        opportunity = VisualOpportunity(
            id="opp-2",
            chapter_index=3,
            section_path="3.2",
            placement=VisualPlacement.inline,
            visual_type="screenshot",
            source_policy="client_assets_only",
            title="Dashboard View",
            prompt="Screenshot of the main dashboard",
            caption="Figure 3.2: Main Dashboard",
            required=True,
            candidate_asset_ids=["asset-1", "asset-2"],
            confidence=0.85,
            rationale="Helps readers visualize the interface",
        )
        assert opportunity.section_path == "3.2"
        assert opportunity.placement == VisualPlacement.inline
        assert opportunity.required is True
        assert len(opportunity.candidate_asset_ids) == 2
        assert opportunity.confidence == 0.85

    def test_opportunity_chapter_index_must_be_positive(self):
        """Test that chapter_index must be >= 1."""
        with pytest.raises(ValidationError):
            VisualOpportunity(
                id="opp-3",
                chapter_index=0,  # Must be >= 1
                visual_type="diagram",
                title="Test",
                prompt="Test prompt",
                caption="Test caption",
            )

    def test_opportunity_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        # Valid confidence
        opp = VisualOpportunity(
            id="opp-4",
            chapter_index=1,
            visual_type="diagram",
            title="Test",
            prompt="Test",
            caption="Test",
            confidence=0.5,
        )
        assert opp.confidence == 0.5

        # Invalid confidence
        with pytest.raises(ValidationError):
            VisualOpportunity(
                id="opp-5",
                chapter_index=1,
                visual_type="diagram",
                title="Test",
                prompt="Test",
                caption="Test",
                confidence=1.5,  # Must be <= 1
            )

    def test_opportunity_placement_enum_values(self):
        """Test all VisualPlacement enum values."""
        placements = [
            VisualPlacement.after_heading,
            VisualPlacement.inline,
            VisualPlacement.end_of_section,
            VisualPlacement.end_of_chapter,
            VisualPlacement.sidebar,
        ]
        for placement in placements:
            opp = VisualOpportunity(
                id="test",
                chapter_index=1,
                visual_type="diagram",
                title="Test",
                prompt="Test",
                caption="Test",
                placement=placement,
            )
            assert opp.placement == placement


class TestVisualPlan:
    """Tests for VisualPlan model."""

    def test_create_empty_plan(self):
        """Test creating an empty visual plan."""
        plan = VisualPlan()
        assert len(plan.opportunities) == 0
        assert len(plan.assets) == 0

    def test_create_plan_with_opportunities(self):
        """Test creating a plan with opportunities."""
        plan = VisualPlan(
            opportunities=[
                VisualOpportunity(
                    id="opp-1",
                    chapter_index=1,
                    visual_type="diagram",
                    title="Test 1",
                    prompt="Prompt 1",
                    caption="Caption 1",
                ),
                VisualOpportunity(
                    id="opp-2",
                    chapter_index=2,
                    visual_type="screenshot",
                    title="Test 2",
                    prompt="Prompt 2",
                    caption="Caption 2",
                ),
            ]
        )
        assert len(plan.opportunities) == 2
        assert plan.opportunities[0].title == "Test 1"
        assert plan.opportunities[1].visual_type == "screenshot"

    def test_create_plan_with_assets(self):
        """Test creating a plan with assets."""
        plan = VisualPlan(
            assets=[
                VisualAsset(
                    id="asset-1",
                    filename="image1.png",
                    media_type="image/png",
                ),
                VisualAsset(
                    id="asset-2",
                    filename="image2.jpg",
                    media_type="image/jpeg",
                ),
            ]
        )
        assert len(plan.assets) == 2
        assert plan.assets[0].filename == "image1.png"

    def test_create_complete_plan(self):
        """Test creating a complete visual plan."""
        asset = VisualAsset(
            id="asset-1",
            filename="architecture.png",
            media_type="image/png",
        )
        opportunity = VisualOpportunity(
            id="opp-1",
            chapter_index=1,
            visual_type="diagram",
            title="Architecture",
            prompt="System architecture diagram",
            caption="Figure 1: Architecture",
            candidate_asset_ids=["asset-1"],
        )
        plan = VisualPlan(
            opportunities=[opportunity],
            assets=[asset],
        )

        assert len(plan.opportunities) == 1
        assert len(plan.assets) == 1
        assert plan.opportunities[0].candidate_asset_ids == ["asset-1"]

    def test_plan_extra_fields_forbidden(self):
        """Test that extra fields are forbidden on plan."""
        with pytest.raises(ValidationError) as exc_info:
            VisualPlan(unknown_field="value")
        assert "extra" in str(exc_info.value).lower()

    def test_plan_serialization(self):
        """Test plan serialization to dict."""
        plan = VisualPlan(
            opportunities=[
                VisualOpportunity(
                    id="opp-1",
                    chapter_index=1,
                    visual_type="diagram",
                    title="Test",
                    prompt="Test prompt",
                    caption="Test caption",
                )
            ],
            assets=[
                VisualAsset(
                    id="asset-1",
                    filename="test.png",
                    media_type="image/png",
                )
            ],
        )
        data = plan.model_dump()

        assert len(data["opportunities"]) == 1
        assert len(data["assets"]) == 1
        assert data["opportunities"][0]["id"] == "opp-1"
        assert data["assets"][0]["id"] == "asset-1"

    def test_plan_deserialization(self):
        """Test plan deserialization from dict."""
        data = {
            "opportunities": [
                {
                    "id": "opp-1",
                    "chapter_index": 2,
                    "visual_type": "chart",
                    "title": "Sales Chart",
                    "prompt": "Bar chart of sales",
                    "caption": "Figure 2: Sales",
                }
            ],
            "assets": [
                {
                    "id": "asset-1",
                    "filename": "chart.png",
                    "media_type": "image/png",
                }
            ],
        }
        plan = VisualPlan.model_validate(data)

        assert len(plan.opportunities) == 1
        assert plan.opportunities[0].visual_type == "chart"
        assert len(plan.assets) == 1
        assert plan.assets[0].filename == "chart.png"

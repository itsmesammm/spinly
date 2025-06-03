from typing import List
from app.models.release import Release


async def calculate_release_similarity(base_release: Release, target_release: Release) -> float:
    """
    Calculates a similarity score between two releases based on weighted matches
    of Style, Label, Year, and Artist.
    """
    score = 0.0

    # Define your weights based on your proposed order of relevance
    # Higher number means higher importance
    WEIGHT_STYLE = 4.0
    WEIGHT_LABEL = 3.0
    WEIGHT_YEAR = 2.0
    WEIGHT_ARTIST = 1.0

    # 1. Styles (most relevant)
    # Compare common styles. The more styles in common, the higher the score.
    if base_release.styles and target_release.styles:
        # Convert lists to sets for efficient intersection
        base_styles_set = set(s.lower() for s in base_release.styles)
        target_styles_set = set(s.lower() for s in target_release.styles)

        common_styles = len(base_styles_set.intersection(target_styles_set))

        # You could normalize this by the number of styles in the base release
        # For simplicity, let's just add common_styles * WEIGHT_STYLE
        score += common_styles * WEIGHT_STYLE

    # 2. Label
    if base_release.label and target_release.label and \
            base_release.label.lower() == target_release.label.lower():
        score += WEIGHT_LABEL

    # 3. Year
    if base_release.year is not None and target_release.year is not None:
        year_diff = abs(base_release.year - target_release.year)
        # Closer years get a higher contribution.
        # Example: 0 diff -> +WEIGHT_YEAR, 1 year diff -> +WEIGHT_YEAR * 0.5, etc.
        # Using a simple inverse relationship: 1 / (1 + difference)
        score += (1 / (1 + year_diff)) * WEIGHT_YEAR

    # 4. Artist (least relevant for 'similar' if not the same artist)
    if base_release.artist and target_release.artist and \
            base_release.artist.lower() == target_release.artist.lower():
        score += WEIGHT_ARTIST

    return score
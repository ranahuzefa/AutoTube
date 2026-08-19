"""Stock candidate filtering and scoring."""

from __future__ import annotations

from .types import StockFilter, StockVideo


def filter_candidates(videos: list[StockVideo], filter: StockFilter) -> list[StockVideo]:
    """Keep candidates suitable for the configured target format."""
    out = []
    for video in videos:
        if not video.url:
            continue
        if filter.orientation == "landscape" and video.width <= video.height:
            continue
        if filter.orientation == "portrait" and video.width >= video.height:
            continue
        if video.width and video.width < filter.min_width:
            continue
        if video.height and video.height < filter.min_height:
            continue
        if video.duration and filter.min_duration and video.duration < filter.min_duration:
            continue
        if video.duration and filter.max_duration and video.duration > filter.max_duration:
            continue
        out.append(video)
    return out


class StockScorer:
    """Deterministic relevance scoring."""

    def score(self, video: StockVideo, filter: StockFilter, query: str = "") -> float:
        score = 0.0

        if video.width > video.height:
            score += 30.0
        elif video.width < video.height:
            score -= 20.0

        if video.width >= filter.min_width and video.height >= filter.min_height:
            score += 25.0
        else:
            score -= 15.0

        if video.duration >= filter.min_duration:
            score += 20.0
        else:
            score -= 15.0

        if video.width and video.height and filter.width and filter.height:
            target_aspect = filter.width / filter.height
            video_aspect = video.width / video.height
            if abs(video_aspect - target_aspect) / target_aspect < 0.15:
                score += 10.0

        if query:
            query_tokens = set(query.lower().split())
            title_tokens = set((video.title or "").lower().split())
            if query_tokens & title_tokens:
                score += 10.0

        return score

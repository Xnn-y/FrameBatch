from framebatch.ffmpeg.probe import (
    _parse_duration,
    _parse_frame_rate,
    _parse_total_frames,
)


def test_parse_video_metadata_prefers_nb_frames() -> None:
    stream = {
        "duration": "4.0",
        "avg_frame_rate": "25/1",
        "nb_frames": "90",
    }

    duration = _parse_duration(stream, {})
    frame_rate = _parse_frame_rate(stream)
    total_frames = _parse_total_frames(stream, duration, frame_rate)

    assert duration == 4.0
    assert frame_rate == 25.0
    assert total_frames == 90


def test_parse_total_frames_falls_back_to_duration_times_rate() -> None:
    stream = {
        "avg_frame_rate": "30000/1001",
        "nb_frames": "N/A",
    }

    total_frames = _parse_total_frames(stream, duration=10.0, frame_rate=_parse_frame_rate(stream))

    assert total_frames == 300

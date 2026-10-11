"""Profile planning: GGUF selection, inference fallback, full repo, runtime kit."""

from stele.hub.planner import default_gguf, plan_profile
from stele.models import PROFILE_FULL, PROFILE_GGUF, PROFILE_INFERENCE, PROFILE_RUNTIME, HubFile

CAPACITY = 25_025_314_816


def _files() -> list[HubFile]:
    return [
        HubFile("model-Q4_K_M.gguf", 100),
        HubFile("model-Q8_0.gguf", 200),
        HubFile("tokenizer.json", 10),
        HubFile("config.json", 2),
        HubFile("README.md", 3),
        HubFile("LICENSE", 4),
        HubFile("image.png", 50),
        HubFile("optimizer.pt", 80),
    ]


def test_gguf_profile_keeps_selected_file_and_ancillary():
    plan = plan_profile(PROFILE_GGUF, _files(), selected_gguf=["model-Q4_K_M.gguf"], capacity_bytes=CAPACITY)
    paths = {item.path for item in plan.files}
    assert paths == {"model-Q4_K_M.gguf", "tokenizer.json", "config.json", "README.md", "LICENSE"}
    assert plan.total_bytes == 119
    assert plan.fallback_note is None
    assert plan.profile_used == PROFILE_GGUF
    assert plan.disc_estimate == 1


def test_no_gguf_falls_back_to_inference_and_says_so():
    files = [
        HubFile("model.safetensors", 10),
        HubFile("config.json", 1),
        HubFile("optimizer.bin", 5),
        HubFile("training_args.bin", 4),
        HubFile("README.md", 2),
    ]
    plan = plan_profile(PROFILE_GGUF, files, selected_gguf=[], capacity_bytes=CAPACITY)
    assert plan.profile_used == PROFILE_INFERENCE
    assert plan.fallback_note
    assert "Inference pack" in plan.fallback_note
    paths = {item.path for item in plan.files}
    assert paths == {"model.safetensors", "config.json", "README.md"}
    assert plan.total_bytes == 13


def test_full_repo_includes_every_path():
    files = _files()
    plan = plan_profile(PROFILE_FULL, files, capacity_bytes=CAPACITY)
    assert {item.path for item in plan.files} == {item.path for item in files}
    assert plan.total_bytes == sum(item.known_size for item in files)


def test_runtime_kit_has_no_model_files():
    plan = plan_profile(PROFILE_RUNTIME, _files(), capacity_bytes=CAPACITY)
    assert plan.files == []
    assert plan.total_bytes == 0


def test_default_gguf_prefers_q4_then_smallest():
    files = _files()
    assert default_gguf(files) == "model-Q4_K_M.gguf"
    only_large = [HubFile("big-Q8_0.gguf", 500), HubFile("small-Q5_K_M.gguf", 50)]
    assert default_gguf(only_large) == "small-Q5_K_M.gguf"
    assert default_gguf([HubFile("config.json", 2)]) is None


def test_gguf_without_a_selection_is_blocked():
    plan = plan_profile(PROFILE_GGUF, _files(), selected_gguf=[], capacity_bytes=CAPACITY)
    assert plan.blocked_reason
    assert "Select at least one GGUF" in plan.blocked_reason

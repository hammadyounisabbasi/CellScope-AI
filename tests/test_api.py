def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_image_analysis(client, cell_image):
    response = client.post("/api/images/analyze", files={"file": ("cells.png", cell_image, "image/png")})
    assert response.status_code == 200, response.text
    data = response.json()
    assert 5 <= data["metrics"]["object_count"] <= 7
    assert data["overlay_png_base64"]
    assert data["mask_png_base64"]


def test_invalid_image_rejected(client):
    response = client.post("/api/images/analyze", files={"file": ("fake.png", b"not an image", "image/png")})
    assert response.status_code == 422


def test_wrong_extension_rejected(client):
    response = client.post("/api/images/analyze", files={"file": ("payload.exe", b"x", "application/octet-stream")})
    assert response.status_code == 415


def test_experiment_analysis(client, csv_data):
    response = client.post("/api/experiments/analyze", files={"file": ("experiment.csv", csv_data, "text/csv")})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["rows"] == 24
    assert data["schema_summary"]["group_column"] == "group"
    assert any(item["feature"] == "area" for item in data["group_comparisons"])


def test_malformed_csv_graceful(client):
    response = client.post("/api/experiments/analyze", files={"file": ("bad.csv", b'"unterminated', "text/csv")})
    assert response.status_code == 422


def test_grounded_chat(client):
    response = client.post("/api/chat", json={"question": "What is BBBC031 microscopy ground truth?"})
    assert response.status_code == 200
    data = response.json()
    assert data["sources"]
    assert data["evidence_sufficient"] is True
    assert "retrieve_scientific_context" in data["tools_used"]
    assert data["workflow_trace"][0]["node"] == "intent_context_analyzer"
    assert data["workflow_trace"][-1]["node"] == "response_composer"


def test_general_results_question_uses_active_context(client):
    response = client.post(
        "/api/chat",
        json={
            "question": "What measurable differences were found?",
            "image_analysis": {"metrics": {"object_count": 4, "mean_area_px": 10, "mean_circularity": 0.8, "foreground_fraction": 0.1}},
            "experiment_analysis": {"observations": ["Two groups were detected."], "group_comparisons": []},
        },
    )
    assert response.status_code == 200
    assert set(response.json()["tools_used"]) >= {"microscopy_image_analysis", "experiment_csv_analysis"}
    assert "AI INTERPRETATION" in response.json()["answer"]


def test_unsupported_chat_admits_limit(client):
    response = client.post("/api/chat", json={"question": "Explain quantum gravity topology"})
    assert response.status_code == 200
    assert response.json()["evidence_sufficient"] is False


def test_chat_accepts_history_for_short_follow_up(client):
    response = client.post(
        "/api/chat",
        json={
            "question": "What does that mean?",
            "image_analysis": {
                "metrics": {"mean_circularity": 0.77},
                "reliability": {"level": "moderate", "notes": []},
            },
            "conversation_history": [
                {"role": "user", "content": "What is the circularity?"},
                {"role": "assistant", "content": "Mean circularity is 0.77."},
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "CIRCULARITY_ANALYSIS" in data["workflow_trace"][0]["intents"]
    assert "approaches 1" in data["answer"]


def test_report_generation(client):
    response = client.post("/api/reports/generate", json={"title": "Test report", "image_analysis": {"filename": "x.png", "method": "test", "metrics": {"object_count": 2}, "reliability": {"level": "test"}}})
    assert response.status_code == 200
    assert "Research assistance only" in response.json()["html"]


def test_report_embeds_visual_results(client):
    tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    response = client.post(
        "/api/reports/generate",
        json={
            "image_analysis": {
                "filename": "cells.png",
                "method": "test",
                "metrics": {"object_count": 2},
                "reliability": {"level": "test"},
                "overlay_png_base64": tiny_png,
                "mask_png_base64": "not-base64\" onerror=\"alert(1)",
            }
        },
    )
    assert response.status_code == 200
    assert "Visual results" in response.json()["html"]
    assert f"data:image/png;base64,{tiny_png}" in response.json()["html"]
    assert "onerror" not in response.json()["html"]

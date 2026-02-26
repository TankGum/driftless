from enum import Enum


class Intent(Enum):
    KNOWLEDGE_QUERY = "knowledge_query"
    ANALYTICS_QUERY = "analytics_query"
    FORECAST_QUERY = "forecast_query"
    SUPPORT_REQUEST = "support_request"
    UNKNOWN = "unknown"


INTENT_KEYWORDS = {
    Intent.KNOWLEDGE_QUERY: [
        "quy trình",
        "tài liệu",
        "hướng dẫn",
        "sop",
        "policy",
        "làm thế nào",
        "như thế nào",
        "cách",
        "bước",
        "quy định",
        "document",
        "spec",
        "flow",
        "báo cáo",
    ],
    Intent.ANALYTICS_QUERY: [
        "kpi",
        "tiến độ",
        "hiệu suất",
        "bug",
        "velocity",
        "tháng này",
        "tuần này",
        "thống kê",
        "report",
        "performance",
        "task",
        "completion",
        "overdue",
        "ai đang",
        "thấp nhất",
        "cao nhất",
        "bao nhiêu",
        "tình trạng",
        "status",
        "target",
        "achievement",
        "hoàn thành",
        "chưa xong",
        "trễ hạn",
        "phân tích",
    ],
    Intent.FORECAST_QUERY: [
        "dự báo",
        "forecast",
        "tháng sau",
        "quý sau",
        "có kịp không",
        "bao lâu",
        "khi nào xong",
    ],
    Intent.SUPPORT_REQUEST: [
        "giúp tôi",
        "hỗ trợ",
        "viết email",
        "draft",
    ],
}


def detect_intent(text: str) -> Intent:
    text_lower = text.lower()
    scores = {intent: 0 for intent in Intent}

    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                scores[intent] += 1

    best_intent = max(scores, key=scores.get)

    if scores[best_intent] == 0:
        return Intent.KNOWLEDGE_QUERY

    return best_intent

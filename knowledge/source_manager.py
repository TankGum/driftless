from core.logger import logger
from database.supabase import supabase
from knowledge.indexer import sync_source


def add_source(url_or_id: str, company_id: str, added_by: int | str) -> tuple[bool, str]:
    source_id, source_type = parse_source(url_or_id)

    if not source_id:
        return False, (
            "❌ Không nhận ra link này.\n\n"
            "Hỗ trợ:\n"
            "• Google Sheets: `docs.google.com/spreadsheets/d/ID`\n"
            "• Google Docs: `docs.google.com/document/d/ID`"
        )

    existing = (
        supabase.table("data_sources")
        .select("id")
        .eq("company_id", company_id)
        .eq("source_id", source_id)
        .execute()
    )

    if existing.data:
        return False, "⚠️ Tài liệu này đã được thêm trước đó rồi."

    try:
        chunks = sync_source(
            f"doc:{source_id}" if source_type == "google_docs" else source_id,
            company_id,
        )
        if chunks == 0:
            return False, "⚠️ Sync thành công nhưng không tìm thấy nội dung. Kiểm tra lại tài liệu."
    except Exception as e:
        return False, (
            f"❌ Không đọc được tài liệu.\n\n"
            f"Lỗi: `{str(e)[:100]}`\n\n"
            "Đảm bảo đã share tài liệu cho service account."
        )

    supabase.table("data_sources").insert(
        {
            "company_id": company_id,
            "source_type": source_type,
            "source_id": source_id,
            "added_by": str(added_by),
            "is_active": True,
        }
    ).execute()

    doc = (
        supabase.table("documents")
        .select("title")
        .eq("source_id", source_id)
        .execute()
    )

    title = doc.data[0]["title"] if doc.data else source_id

    supabase.table("data_sources").update(
        {"title": title}
    ).eq("source_id", source_id).execute()

    return True, f"✅ Đã thêm và index thành công!\n *{title}* ({chunks} chunks)"


def remove_source(url_or_id: str, company_id: str) -> tuple[bool, str]:
    source_id, _ = parse_source(url_or_id)

    if not source_id:
        return (
            False,
            "❌ Link không hợp lệ. Paste đúng link Google Sheets hoặc Docs nhé.",
        )

    result = (
        supabase.table("data_sources")
        .update({"is_active": False})
        .eq("company_id", company_id)
        .eq("source_id", source_id)
        .execute()
    )

    if result.data:
        doc = (
            supabase.table("documents")
            .select("id, title")
            .eq("source_id", source_id)
            .execute()
        )

        if doc.data:
            supabase.table("document_chunks").delete().eq(
                "document_id", doc.data[0]["id"]
            ).execute()
            title = doc.data[0].get("title", source_id)
            return True, f"✅ Đã xóa *{title}* khỏi knowledge base."

        return True, "✅ Đã xóa tài liệu khỏi knowledge base."

    return False, "❌ Không tìm thấy tài liệu này. Dùng /listdocs để xem danh sách."


def list_sources(company_id: str) -> str:
    result = (
        supabase.table("data_sources")
        .select("*")
        .eq("company_id", company_id)
        .eq("is_active", True)
        .order("created_at")
        .execute()
    )

    if not result.data:
        return " Chưa có tài liệu nào được thêm."

    lines = [f" *Tài liệu đang được index ({len(result.data)} nguồn):*\n"]
    for i, src in enumerate(result.data, 1):
        title = src['title'] or src['source_id']
        source_id = src['source_id']
        lines.append(
            f"{i}. *{title}*\n"
            f"   Type: {src['source_type']}\n"
            f"   ID: {source_id}\n"
        )
    lines.append("Dùng /removedoc [link] để xóa tài liệu")
    return "\n".join(lines)


def resync_all_sources(company_id: str) -> str:
    result = (
        supabase.table("data_sources")
        .select("*")
        .eq("company_id", company_id)
        .eq("is_active", True)
        .execute()
    )

    if not result.data:
        return "Chưa có tài liệu nào để sync."

    success = 0
    failed = 0
    for src in result.data:
        try:
            source_id = (
                f"doc:{src['source_id']}"
                if src["source_type"] == "google_docs"
                else src["source_id"]
            )
            sync_source(source_id, company_id)

            supabase.table("data_sources").update(
                {"last_synced": "now()"}
            ).eq("id", src["id"]).execute()

            success += 1
        except Exception as e:
            logger.error(f"Sync failed for {src['source_id']}: {e}")
            failed += 1

    return (
        f" Sync hoàn thành!\n"
        f"✅ Thành công: {success}\n"
        f"❌ Thất bại: {failed}"
    )


def parse_source(url_or_id: str) -> tuple[str, str]:
    url = url_or_id.strip()

    if "spreadsheets/d/" in url:
        try:
            source_id = url.split("spreadsheets/d/")[1].split("/")[0]
            return source_id, "google_sheets"
        except Exception:
            pass

    if "document/d/" in url:
        try:
            source_id = url.split("document/d/")[1].split("/")[0]
            return source_id, "google_docs"
        except Exception:
            pass

    if len(url) > 20 and "/" not in url:
        return url, "google_sheets"

    return None, None

from backend.app.models.schemas import ProductGroupRecord, SessionRecord


def recent_groups(
    groups: list[ProductGroupRecord],
    sessions: list[SessionRecord],
    n: int,
    min_count: int,
) -> tuple[list[SessionRecord], list[ProductGroupRecord]]:
    recent_sessions = sorted(sessions, key=lambda item: item.session_index)[-n:]
    recent_ids = {session.id for session in recent_sessions}
    products: list[ProductGroupRecord] = []

    for group in groups:
        appear_count = len(recent_ids.intersection(group.appeared_session_ids))
        if appear_count >= min_count:
            products.append(
                group.model_copy(
                    update={
                        "appeared_session_ids": [
                            session_id
                            for session_id in group.appeared_session_ids
                            if session_id in recent_ids
                        ],
                        "appeared_sessions": [
                            session.name
                            for session in recent_sessions
                            if session.id in group.appeared_session_ids
                        ],
                        "appear_count": appear_count,
                        "total_appear_count": group.total_appear_count,
                    }
                )
            )

    products.sort(key=lambda item: (-item.appear_count, item.product_group_id))
    return recent_sessions, products


def top_products(groups: list[ProductGroupRecord], limit: int) -> list[ProductGroupRecord]:
    return sorted(groups, key=lambda item: (-item.appear_count, item.product_group_id))[:limit]


def session_stats(
    groups: list[ProductGroupRecord],
    sessions: list[SessionRecord],
) -> list[dict]:
    first_appearance = {
        group.id: min(group.appeared_session_ids)
        for group in groups
        if group.appeared_session_ids
    }
    rows: list[dict] = []

    for session in sorted(sessions, key=lambda item: item.session_index):
        session_groups = [
            group for group in groups if session.id in group.appeared_session_ids
        ]
        repeated = [group for group in session_groups if group.appear_count > 1]
        new_groups = [
            group for group in session_groups if first_appearance.get(group.id) == session.id
        ]
        rows.append(
            {
                "session_id": session.id,
                "session_name": session.name,
                "image_count": session.image_count,
                "product_count": len(session_groups),
                "repeated_product_count": len(repeated),
                "new_product_count": len(new_groups),
                "duplicate_rate": round(len(repeated) / len(session_groups), 4)
                if session_groups
                else 0,
            }
        )

    return rows

from backend.app.models.schemas import ImageRecord, ProductGroupRecord, SessionRecord


def match_product_groups(
    images: list[ImageRecord],
    sessions: list[SessionRecord],
    threshold: int = 8,
) -> list[ProductGroupRecord]:
    groups: list[list[ImageRecord]] = []
    tree = HashBKTree()

    for image in images:
        image_hash = parse_image_hash(image.image_hash)
        if image_hash is None:
            groups.append([image])
            continue

        match = tree.find_nearest(image_hash, threshold)
        if match is not None:
            _, best_group_index = match
            groups[best_group_index].append(image)
        else:
            groups.append([image])
            best_group_index = len(groups) - 1
        tree.insert(image_hash, best_group_index)

    session_names = {session.id: session.name for session in sessions}
    product_groups = [
        build_product_group(group_id=index, images=group, session_names=session_names)
        for index, group in enumerate(groups, start=1)
    ]

    return sorted(
        product_groups,
        key=lambda group: (-group.appear_count, group.product_group_id),
    )


def parse_image_hash(image_hash: str | None) -> int | None:
    if not image_hash:
        return None
    try:
        return int(image_hash, 16)
    except ValueError:
        return None


def hash_distance(hash_a: int, hash_b: int) -> int:
    return (hash_a ^ hash_b).bit_count()


class HashBKTreeNode:
    def __init__(self, image_hash: int, group_index: int) -> None:
        self.image_hash = image_hash
        self.group_indices = {group_index}
        self.children: dict[int, HashBKTreeNode] = {}


class HashBKTree:
    def __init__(self) -> None:
        self.root: HashBKTreeNode | None = None

    def insert(self, image_hash: int, group_index: int) -> None:
        if self.root is None:
            self.root = HashBKTreeNode(image_hash, group_index)
            return

        node = self.root
        while True:
            distance = hash_distance(image_hash, node.image_hash)
            if distance == 0:
                node.group_indices.add(group_index)
                return
            child = node.children.get(distance)
            if child is None:
                node.children[distance] = HashBKTreeNode(image_hash, group_index)
                return
            node = child

    def find_nearest(self, image_hash: int, threshold: int) -> tuple[int, int] | None:
        if self.root is None:
            return None

        best: tuple[int, int] | None = None
        stack = [self.root]
        while stack:
            node = stack.pop()
            distance = hash_distance(image_hash, node.image_hash)
            if distance <= threshold:
                group_index = min(node.group_indices)
                if best is None or (distance, group_index) < best:
                    best = (distance, group_index)

            lower = distance - threshold
            upper = distance + threshold
            for edge_distance, child in node.children.items():
                if lower <= edge_distance <= upper:
                    stack.append(child)

        return best


def build_product_group(
    group_id: int,
    images: list[ImageRecord],
    session_names: dict[int, str],
) -> ProductGroupRecord:
    appeared_session_ids = sorted({image.session_id for image in images})
    appeared_sessions = [
        session_names.get(session_id, str(session_id))
        for session_id in appeared_session_ids
    ]

    return ProductGroupRecord(
        id=group_id,
        product_group_id=f"PG_{group_id:06d}",
        representative_image=images[0].file_path,
        images=images,
        appeared_sessions=appeared_sessions,
        appeared_session_ids=appeared_session_ids,
        appear_count=len(appeared_session_ids),
        total_appear_count=len(appeared_session_ids),
    )

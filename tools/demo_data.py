"""Create and remove the local demo shop used by the simulators."""

import argparse
import asyncio
import os
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.models.conversation_events import ConversationEvents
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.sales import Sale
from app.models.shop import Shop

DEMO_PHONE: Final = os.getenv(
    "DEFAULT_SIMULATOR_PHONE",
    settings.whatsapp_phone_number_id or "254712345678",
)
LEGACY_DEMO_PHONE: Final = "+254700000099"
DEMO_SHOP_NAME: Final = "SokoFlow Demo Shop"


@dataclass(frozen=True)
class DemoProduct:
    name: str
    sku: str
    price: Decimal
    quantity: int


DEMO_PRODUCTS: Final[tuple[DemoProduct, ...]] = (
    DemoProduct("Sugar 1kg", "DEMO-SUGAR-1KG", Decimal("180.00"), 25),
    DemoProduct("Unga 2kg", "DEMO-UNGA-2KG", Decimal("250.00"), 20),
    DemoProduct("Milk 500ml", "DEMO-MILK-500ML", Decimal("65.00"), 30),
    DemoProduct("Bread", "DEMO-BREAD", Decimal("70.00"), 15),
    DemoProduct("Cooking Oil 1L", "DEMO-OIL-1L", Decimal("320.00"), 10),
)


def _ensure_local_environment() -> None:
    if settings.app_env.lower() in {"production", "prod"}:
        raise RuntimeError("Demo data commands are disabled when APP_ENV is production.")


def _upgrade_database() -> None:
    alembic_executable = Path(sys.executable).with_name("alembic")
    if not alembic_executable.is_file():
        raise RuntimeError(f"Alembic executable not found next to {sys.executable}.")
    subprocess.run(
        [str(alembic_executable), "upgrade", "head"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )


async def _delete_demo_data(session: AsyncSession, phone: str) -> bool:
    shop = await session.scalar(select(Shop).where(Shop.phone == phone))
    if shop is None:
        return False
    if shop.name != DEMO_SHOP_NAME:
        raise RuntimeError(
            f"{phone} belongs to {shop.name!r}, not the SokoFlow demo shop; refusing to delete it."
        )

    product_ids = select(Product.id).where(Product.shop_id == shop.id)
    await session.execute(delete(Sale).where(Sale.shop_id == shop.id))
    await session.execute(delete(Inventory).where(Inventory.product_id.in_(product_ids)))
    await session.execute(delete(Product).where(Product.shop_id == shop.id))
    await session.execute(delete(ConversationEvents).where(ConversationEvents.phone == phone))
    await session.delete(shop)
    return True


async def seed_demo_data() -> None:
    _ensure_local_environment()
    async with SessionLocal() as session:
        existing_shop = await session.scalar(select(Shop).where(Shop.phone == DEMO_PHONE))
        if existing_shop is not None and existing_shop.name != DEMO_SHOP_NAME:
            raise RuntimeError(
                f"{DEMO_PHONE} belongs to {existing_shop.name!r}, not the SokoFlow demo shop; "
                "refusing to modify it."
            )

        if DEMO_PHONE != LEGACY_DEMO_PHONE:
            await _delete_demo_data(session, LEGACY_DEMO_PHONE)
        if await _delete_demo_data(session, DEMO_PHONE):
            await session.flush()
        shop = Shop(phone=DEMO_PHONE, name=DEMO_SHOP_NAME, locale="en")
        session.add(shop)
        await session.flush()

        for demo_product in DEMO_PRODUCTS:
            product = Product(
                shop_id=shop.id,
                name=demo_product.name,
                sku=demo_product.sku,
                price=demo_product.price,
            )
            session.add(product)
            await session.flush()
            session.add(Inventory(product_id=product.id, quantity=demo_product.quantity))

        await session.commit()

    print(f"Seeded {DEMO_SHOP_NAME} ({DEMO_PHONE}) with {len(DEMO_PRODUCTS)} products.")


async def clean_demo_data() -> None:
    _ensure_local_environment()
    async with SessionLocal() as session:
        deleted = await _delete_demo_data(session, DEMO_PHONE)
        await session.commit()

    if deleted:
        print(f"Removed {DEMO_SHOP_NAME} ({DEMO_PHONE}) and its demo data.")
    else:
        print("No SokoFlow demo data found.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seed", "clean"))
    return parser


async def _run(action: str) -> None:
    try:
        _ensure_local_environment()
        await asyncio.to_thread(_upgrade_database)
        if action == "seed":
            await seed_demo_data()
        else:
            await clean_demo_data()
    finally:
        await engine.dispose()


def main() -> None:
    args = _build_parser().parse_args()
    try:
        asyncio.run(_run(args.action))
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

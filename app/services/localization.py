from collections.abc import Mapping
from typing import Any

from app.fsm.models import MessageKey

SUPPORTED_LOCALES = frozenset({"en", "sw"})

_MESSAGES: dict[MessageKey, dict[str, str]] = {
    MessageKey.FLOW_CANCELLED: {
        "en": "Flow cancelled. How can I help you today?",
        "sw": "Mchakato umeghairiwa. Ninaweza kukusaidia vipi leo?",
    },
    MessageKey.TOO_MANY_INVALID: {
        "en": (
            "Too many invalid attempts. I've cancelled this request so we can start fresh. "
            "Type 'add product' to try again."
        ),
        "sw": (
            "Majaribio mengi si sahihi. Nimeghairi ombi hili ili tuanze upya. "
            "Andika 'add product' kujaribu tena."
        ),
    },
    MessageKey.UNKNOWN_INTENT: {
        "en": "Type 'add product', 'record sale', or 'check stock' to begin.",
        "sw": "Andika 'add product', 'record sale', au 'check stock' kuanza.",
    },
    MessageKey.START_SALE: {
        "en": "Great, let's record a sale. What product was sold?",
        "sw": "Sawa, hebu turekodi mauzo. Ni bidhaa gani iliuzwa?",
    },
    MessageKey.START_STOCK_CHECK: {
        "en": "Sure, let's check stock. Which product would you like to lookup?",
        "sw": "Sawa, hebu tuangalie stoo. Unataka kuangalia bidhaa gani?",
    },
    MessageKey.REPORT_GENERATING: {
        "en": (
            "Great. The report is being generated. Just a moment while we process "
            "and send it to you."
        ),
        "sw": "Sawa. Ripoti inaundwa. Subiri kidogo tunapoichakata na kukutumia.",
    },
    MessageKey.START_ADD_PRODUCT: {
        "en": "Great, let's add a product. What is the product name?",
        "sw": "Sawa, hebu tuongeze bidhaa. Jina la bidhaa ni lipi?",
    },
    MessageKey.ASK_PRICE: {
        "en": "Nice. What is the price in KES?",
        "sw": "Vizuri. Bei ni kiasi gani kwa KES?",
    },
    MessageKey.ASK_STOCK_QUANTITY: {
        "en": "Got it. How many units are in stock?",
        "sw": "Nimekupata. Kuna vipande vingapi stoo?",
    },
    MessageKey.CONFIRM_PRODUCT: {
        "en": (
            "Please confirm: {product_name} at KES {price:.2f}, quantity {quantity}. "
            "Reply Yes or No."
        ),
        "sw": ("Thibitisha: {product_name} kwa KES {price:.2f}, kiasi {quantity}. Jibu Yes au No."),
    },
    MessageKey.PRODUCT_CANCELLED: {
        "en": "No problem. I cancelled the product flow.",
        "sw": "Hakuna shida. Nimeghairi mchakato wa bidhaa.",
    },
    MessageKey.PRODUCT_ADDED: {
        "en": "Product added: {product_name} at KES {price:.2f} with opening quantity {quantity}.",
        "sw": (
            "Bidhaa imeongezwa: {product_name} kwa KES {price:.2f} na kiasi cha kuanzia {quantity}."
        ),
    },
    MessageKey.ASK_SALE_QUANTITY: {
        "en": "Got it. How many units sold?",
        "sw": "Nimekupata. Vipande vingapi viliuzwa?",
    },
    MessageKey.ASK_QUANTITY: {
        "en": "Got it. How many units?",
        "sw": "Nimekupata. Vipande vingapi?",
    },
    MessageKey.PRODUCT_NOT_FOUND: {
        "en": (
            "I couldn't find a matching product.\nPlease check the name and try again, "
            "or type *'cancel'* to stop."
        ),
        "sw": (
            "Sikupata bidhaa inayolingana.\nAngalia jina ujaribu tena, "
            "au andika *'cancel'* kusitisha."
        ),
    },
    MessageKey.PRODUCT_CHOICES: {
        "en": (
            "Which product did you mean?\n\n{choices}\n\nReply with a number from 1 to {count}."
        ),
        "sw": ("Ulikusudia bidhaa gani?\n\n{choices}\n\nJibu kwa nambari kutoka 1 hadi {count}."),
    },
    MessageKey.CONFIRM_SALE: {
        "en": (
            "Confirm Sale:\n- Product: {product_name}\n- Quantity: {quantity}\n"
            "- Total: KES {total:.2f}\n\nReply *yes* to record or *no* to cancel."
        ),
        "sw": (
            "Thibitisha Mauzo:\n- Bidhaa: {product_name}\n- Kiasi: {quantity}\n"
            "- Jumla: KES {total:.2f}\n\nJibu *yes* kurekodi au *no* kughairi."
        ),
    },
    MessageKey.SALE_CANCELLED: {
        "en": "No problem. I cancelled the sale flow.",
        "sw": "Hakuna shida. Nimeghairi mchakato wa mauzo.",
    },
    MessageKey.SALE_RECORDED: {
        "en": (
            "Sale recorded: *{product_name}* ({quantity} units).\n"
            "Stock remaining: *{remaining_stock}* units.{low_stock}"
        ),
        "sw": (
            "Mauzo yamerekodiwa: *{product_name}* ({quantity} vipande).\n"
            "Stoo iliyobaki: *{remaining_stock}* vipande.{low_stock}"
        ),
    },
    MessageKey.STOCK_NOT_FOUND: {
        "en": "I could not find a product in the inventory with that name.",
        "sw": "Sikupata bidhaa yenye jina hilo kwenye stoo.",
    },
    MessageKey.STOCK_REMAINING: {
        "en": "Remaining stock for {product_name}: {quantity} units",
        "sw": "Stoo iliyobaki ya {product_name}: {quantity} vipande",
    },
    MessageKey.PRODUCT_NAME_INVALID: {
        "en": "Product name must be between 2 and 100 characters.",
        "sw": "Jina la bidhaa lazima liwe na herufi 2 hadi 100.",
    },
    MessageKey.PRICE_INVALID: {
        "en": "Please enter a valid price, e.g. '150', 'KES 150', or '150/='.",
        "sw": "Weka bei sahihi, kwa mfano '150', 'KES 150', au '150/='.",
    },
    MessageKey.PRICE_NON_POSITIVE: {
        "en": "Price must be greater than 0",
        "sw": "Bei lazima iwe zaidi ya 0",
    },
    MessageKey.QUANTITY_INVALID: {
        "en": "Please enter a whole number, e.g. 0, 1, or 25.",
        "sw": "Weka nambari kamili, kwa mfano 0, 1, au 25.",
    },
    MessageKey.QUANTITY_NEGATIVE: {
        "en": "Quantity cannot be negative.",
        "sw": "Kiasi hakiwezi kuwa hasi.",
    },
    MessageKey.CONFIRMATION_INVALID: {
        "en": "Please reply with Yes/Y/Ndio/1 or No/N/Zii/2.",
        "sw": "Jibu Yes/Y/Ndio/1 au No/N/Zii/2.",
    },
    MessageKey.UNKNOWN_ERROR: {
        "en": "{message}",
        "sw": "{message}",
    },
    MessageKey.INVALID_CHOICE: {
        "en": "Invalid Choice",
        "sw": "Chaguo si sahihi",
    },
    MessageKey.QUANTITY_TOO_LOW: {
        "en": "Please enter a quantity greater than 0.",
        "sw": "Weka kiasi kikubwa kuliko 0.",
    },
    MessageKey.SESSION_CONTEXT_LOST: {
        "en": "I lost some product details. Type 'add product' to start again.",
        "sw": "Nimepoteza maelezo ya bidhaa. Andika 'add product' kuanza tena.",
    },
    MessageKey.SHOP_NOT_FOUND: {
        "en": "I couldn't find your shop profile. Please contact support.",
        "sw": "Sikupata wasifu wa duka lako. Tafadhali wasiliana na msaada.",
    },
    MessageKey.INSUFFICIENT_STOCK: {
        "en": (
            "Insufficient stock! Only *{available}* units of {product_name} remaining. "
            "Please enter a valid quantity."
        ),
        "sw": (
            "Stoo haitoshi! Zimesalia vipande *{available}* vya {product_name}. Weka kiasi sahihi."
        ),
    },
}


def render_message(
    message_key: MessageKey,
    locale: str,
    params: Mapping[str, Any] | None = None,
) -> str:
    selected_locale = locale if locale in SUPPORTED_LOCALES else "en"
    template = _MESSAGES[message_key].get(selected_locale, _MESSAGES[message_key]["en"])
    values = dict(params or {})

    if message_key is MessageKey.SALE_RECORDED:
        values["low_stock"] = (
            (
                "\n*Low Stock Alert*: Only {remaining_stock} units left."
                if selected_locale == "en"
                else "\n*Tahadhari ya Stoo ya Chini*: Zimesalia vipande {remaining_stock} tu."
            )
            if values.get("entered_low_stock")
            else ""
        ).format(**values)
    if message_key is MessageKey.PRODUCT_CHOICES:
        candidates = values.get("candidates", [])
        values["choices"] = "\n".join(
            f"{index}. {candidate['name']} — {candidate['price']}"
            for index, candidate in enumerate(candidates, start=1)
        )
        values["count"] = len(candidates)
    return template.format(**values)

import factory

from app.models import Product


class ProductFactory(factory.Factory):
    class Meta:
        model = Product

    name = factory.Faker("word")
    price = factory.Faker("pydecimal", left_digits=4, right_digits=2, positive=True)
    sku = factory.Sequence(lambda n: f"SKU-{n + 1:06d}")

    @classmethod
    def as_dict(cls, **kwargs):
        obj = cls.build(**kwargs)
        return {"name": obj.name, "price": obj.price, "sku": obj.sku}

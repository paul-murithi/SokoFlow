import factory

from app.models import Product, Shop


class ProductFactory(factory.Factory):
    class Meta:  # type: ignore
        model = Product

    name = factory.Faker("word")
    price = factory.Faker("pydecimal", left_digits=4, right_digits=2, positive=True)

    @classmethod
    def as_dict(cls, **kwargs):
        obj = cls.build(**kwargs)
        return {"name": obj.name, "price": str(obj.price)}


class ShopFactory(factory.Factory):
    class Meta:  # type: ignore
        model = Shop

    phone = factory.Faker("bothify", text="+1-###-###-####")
    name = factory.Faker("company")

    @classmethod
    def as_dict(cls, **kwargs):
        obj = cls.build(**kwargs)
        return {"name": obj.name, "phone": obj.phone}

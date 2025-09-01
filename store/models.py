# store/models.py
from tortoise import fields, models


class Token(models.Model):
    """
    ERC-20 metadata (unique by address).
    """
    id = fields.IntField(pk=True)
    address = fields.CharField(max_length=42, unique=True, index=True)
    symbol = fields.CharField(max_length=64, null=True)
    decimals = fields.IntField(null=True)

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "tokens"

    def __str__(self):
        return f"<Token {self.symbol or ''} {self.address}>"


class Pool(models.Model):
    """
    Uniswap V3 pool (unique by address). Fee may be unknown at first.
    """
    id = fields.IntField(pk=True)
    address = fields.CharField(max_length=42, unique=True, index=True)

    token0 = fields.ForeignKeyField("models.Token", related_name="as_token0")
    token1 = fields.ForeignKeyField("models.Token", related_name="as_token1")

    # Uniswap V3 fee in uint24 (e.g., 3000, 10000); nullable if not fetched yet
    fee = fields.IntField(null=True)

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "pools"
        indexes = (("address",),)

    def __str__(self):
        return f"<Pool {self.address}>"


class Swap(models.Model):
    """
    Uniswap V3 Swap event.
    Large on-chain ints stored as strings to avoid 64-bit overflow (sqrtPriceX96, liquidity).
    """
    id = fields.IntField(pk=True)
    pool = fields.ForeignKeyField("models.Pool", related_name="swaps")

    block_number = fields.IntField(index=True)
    tx_hash = fields.CharField(max_length=66)       # 0x + 64 hex
    log_index = fields.IntField()

    sender = fields.CharField(max_length=42, null=True, index=True)
    recipient = fields.CharField(max_length=42, null=True, index=True)

    amount0_raw = fields.CharField(max_length=100) #signed int256 -> Python int fits; DB is 64-bit
    amount1_raw = fields.CharField(max_length=100) #

    sqrt_price_x96 = fields.CharField(max_length=100)  # uint160 as decimal string
    liquidity = fields.CharField(max_length=100)       # uint128 as decimal string
    tick = fields.IntField(null=True)

    # Block timestamp (UTC) you resolve via w3.eth.get_block
    ts = fields.DatetimeField(null=True, index=True)

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "swaps"
        unique_together = (("tx_hash", "log_index"),)
        indexes = (("pool_id", "block_number"), ("tx_hash", "log_index"))

    def __str__(self):
        return f"<Swap {self.tx_hash}@{self.log_index} pool={self.pool_id}>"


class Transfer(models.Model):
    """
    ERC-20 Transfer event.
    Store raw value as string (uint256 can exceed bigint).
    """
    id = fields.IntField(pk=True)
    token = fields.ForeignKeyField("models.Token", related_name="transfers")

    block_number = fields.IntField(index=True)
    tx_hash = fields.CharField(max_length=66)
    log_index = fields.IntField()

    from_addr = fields.CharField(max_length=42, index=True)
    to_addr = fields.CharField(max_length=42, index=True)

    value_raw = fields.CharField(max_length=100)  # uint256 as decimal string
    ts = fields.DatetimeField(null=True, index=True)

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "transfers"
        unique_together = (("tx_hash", "log_index"),)
        indexes = (("token_id", "block_number"), ("from_addr",), ("to_addr",))

    def __str__(self):
        return f"<Transfer {self.tx_hash}@{self.log_index} token={self.token_id}>"

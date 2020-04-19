import logging
import json
import requests
import discord
import dataclasses
import datetime

from discord.ext import commands

from ovisbot.exceptions import CryptoHackApiException
from ovisbot.helpers import success, escape_md
from ovisbot.db_models import CryptoHackUserMapping

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Score:
    username: str
    global_rank: int
    points: int
    total_points: int
    challs_solved: int
    total_challs: int
    num_users: int

    @classmethod
    def parse(cls, raw):
        # username:global_rank:points:total_points:challs_solved:total_challs:num_users
        spl = raw.split(":")
        assert len(spl) == 7
        username = spl.pop(0)
        return cls(*([username] + list(map(int, spl))))


class CryptoHack(commands.Cog):
    DISCORD_TOKEN_API_URL = "https://cryptohack.org/discord_token/{0}/"
    USER_SCORE_API_URL = "https://cryptohack.org/wechall/userscore/"
    USER_URL = "https://cryptohack.org/user/{0}/"

    def __init__(self, bot):
        self.bot = bot

    def _get_cryptohack_score(self, cryptohack_user):
        """
        Returns score of given user.
        """
        req = requests.get(
            CryptoHack.USER_SCORE_API_URL, params={"username": cryptohack_user}
        )
        res = req.text

        if "failed" in res:
            raise CryptoHackApiException

        return Score.parse(res)

    @commands.group()
    async def cryptohack(self, ctx):
        """
        Collection of CryptoHack commands
        """
        if ctx.invoked_subcommand is None:
            await ctx.send("Invalid command passed. Use `!help`.")

    @cryptohack.command()
    async def connect(self, ctx, token=None):
        """
        Link your CryptoHack account
        """
        if token is None:
            msg = (
                "Εν μου έδωκες token! Πάεννε στο https://cryptohack.org/user/ "
                "τζαι πιαστο token που εν κάτω κάτω! Μια ζωη να σας παρατζέλλω δαμέσα!"
            )
            await ctx.send(msg)
        else:
            token = token.replace("/", "").replace(".", "").replace("%", "")
            req = requests.get(CryptoHack.DISCORD_TOKEN_API_URL.format(token))
            res = json.loads(req.content)

            if "error" in res:
                raise CryptoHackApiException(res["error"])

            cryptohack_user = res["user"]
            CryptoHackUserMapping(
                cryptohack_user=cryptohack_user, discord_user_id=ctx.author.id
            ).save()
            await ctx.send(f"Linked CryptoHack as {cryptohack_user}!")
            await success(ctx.message)

    @cryptohack.command()
    async def disconnect(self, ctx):
        """
        Disconecct your CryptoHack account
        """
        cryptohack_mapping = CryptoHackUserMapping.objects.get(
            {"discord_user_id": ctx.author.id}
        )
        cryptohack_mapping.delete()
        await success(ctx.message)

    @cryptohack.command()
    async def stats(self, ctx, user=None):
        """
        Show your CryptoHack stats or any given user's
        """
        if user is None:
            user_id = ctx.author.id
        else:
            user_id = next((m.id for m in ctx.message.mentions), None)
            if user_id is None:
                return

        cryptohack_mapping = CryptoHackUserMapping.objects.get(
            {"discord_user_id": user_id}
        )
        score = self._get_cryptohack_score(cryptohack_mapping.cryptohack_user)

        await ctx.send(
            embed=discord.Embed(
                title=score.username,
                url=CryptoHack.USER_URL.format(score.username),
                color=0xFEB32B,
            )
            .add_field(
                name="Rank",
                value=f"{score.global_rank} / {score.num_users}",
                inline=False,
            )
            .add_field(
                name="Score",
                value=f"{score.points} / {score.total_points}",
                inline=False,
            )
            .add_field(
                name="Solves",
                value=f"{score.challs_solved} / {score.total_challs}",
                inline=False,
            )
        )

    @cryptohack.command()
    async def scoreboard(self, ctx):
        """
        Displays internal CryptoHack scoreboard.
        """
        limit = 10
        mappings = CryptoHackUserMapping.objects.all()
        scores = [
            (
                escape_md(self.bot.get_user(mapping.discord_user_id).name),
                self._get_cryptohack_score(mapping.cryptohack_user),
            )
            for mapping in mappings
        ][:limit]

        scores = sorted(scores, key=lambda s: s[1].points, reverse=True)
        scoreboard = "\n".join(
            "{0}. **{1}**\t{2}".format(idx + 1, s[0], s[1].points)
            for idx, s in enumerate(scores)
        )
        embed = discord.Embed(
            title="CryptoHack Scoreboard",
            colour=discord.Colour(0xFEB32B),
            url="https://cryptohack.org/",
            description=scoreboard,
            timestamp=datetime.datetime.now(),
        )

        embed.set_thumbnail(url="https://cryptohack.org/static/img/main.png")
        embed.set_footer(
            text="CYberMouflons", icon_url="https://i.ibb.co/yW2mYjq/cybermouflons.png",
        )

        await ctx.send(embed=embed)

    @scoreboard.error
    @disconnect.error
    @connect.error
    @stats.error
    async def generic_error_handler(self, ctx, error):
        if isinstance(error.original, CryptoHackUserMapping.DoesNotExist):
            await ctx.channel.send(
                "Ρε λεβεντη... εν βρίσκω συνδεδεμένο CryptoHack account! (`!cryptohack connect <token>`)"
            )
        elif isinstance(error.original, CryptoHackApiException):
            await ctx.channel.send("Ούπς... κατι επήε λάθος ρε τσιάκκο!")


def setup(bot):
    bot.add_cog(CryptoHack(bot))

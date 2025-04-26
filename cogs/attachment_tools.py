from enum import Enum
import discord
from discord.ext import commands


class FailureReason(Enum):
    UNKNOWN = "Catch-all Unknown Reason"
    NO_ATTACHMENTS = "The post has no attachments.",
    USER_CANCELLED = "The operation was cancelled."

    def __init__(self, reason: str):
        self.reason = reason


class IndexSelectModal(discord.ui.Modal, title="Select Attachment by Index"):
    def __init__(self, num_of_attachments: int):
        super().__init__()
        self.num_attachments = num_of_attachments
        self.index_input = discord.ui.TextInput(
            label=f"Index to modify (1-{num_of_attachments})",
            style=discord.TextStyle.short,
            required=True,
            min_length=1,
            max_length=2
        )
        self.interaction = None
        self.answer = -1
        self.add_item(self.index_input)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # TODO: currently this causes an ungraceful "something went wrong" message that takes a few seconds.
        #  figure out how to make that instant and graceful with a custom message.
        resp = str(self.index_input)
        return resp.isnumeric() and 1 <= int(resp) <= self.num_attachments

    async def on_submit(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.answer = int(str(self.index_input)) - 1
        self.stop()


class ConfirmDenyView(discord.ui.View):
    def __init__(self):
        super().__init__()
        confirm_button = discord.ui.Button(
            label="Yes, continue",
            style=discord.ButtonStyle.primary
        )
        cancel_button = discord.ui.Button(
            label="No, cancel",
            style=discord.ButtonStyle.secondary
        )
        confirm_button.callback = self.on_confirm
        cancel_button.callback = self.on_cancel
        self.add_item(confirm_button)
        self.add_item(cancel_button)
        self.interaction = None
        self.result = None

    async def on_interact(self, interaction: discord.Interaction, result: bool):
        self.result = result
        self.interaction = interaction
        # This was supposed to remove the ephemeral message, but it causes an error
        #await interaction.delete_original_response()
        self.stop()

    async def on_confirm(self, interaction: discord.Interaction):
        await self.on_interact(interaction, True)

    async def on_cancel(self, interaction: discord.Interaction):
        await self.on_interact(interaction, False)


async def select_attachment(interaction: discord.Interaction, message: discord.Message) -> tuple[discord.Interaction, discord.Attachment | FailureReason]:
    """
    Selects an attachment from an image, with confirmation message.

    :param interaction:
    :param message: The message that was interacted with.
    :return: The current interaction for chaining, and either the the discord.Attachment selected or the FailureReason
    """

    if len(message.attachments) == 0:
        # Early end because no attachments
        return interaction, FailureReason.NO_ATTACHMENTS

    # No need to ask for an index when there's only one
    if len(message.attachments) == 1:
        selected_attachment: discord.Attachment = message.attachments[0]
    else:
        index_form = IndexSelectModal(len(message.attachments))
        await interaction.response.send_modal(index_form)
        await index_form.wait()
        idx = index_form.answer
        selected_attachment: discord.Attachment = message.attachments[idx]
        # Discord interactions can only be used once, so carry it forward.
        interaction = index_form.interaction

    # Build and send confirmation message
    selected_preview = discord.Embed().set_image(url=selected_attachment.url)
    cdview = ConfirmDenyView()
    await interaction.response.send_message(
        content="This attachment will be edited. Continue?",
        embed=selected_preview,
        ephemeral=True,
        view=cdview)

    await cdview.wait()
    return interaction, selected_attachment if cdview.result else FailureReason.USER_CANCELLED


class AttachmentTools(commands.Cog, name="attachment_tools"):
    def __init__(self, bot) -> None:
        self.bot = bot
        modify_attachments_command = discord.app_commands.ContextMenu(
            name="Modify attachments", callback=self.modify_post
        )
        self.bot.tree.add_command(modify_attachments_command)

    @commands.has_permissions(manage_messages=True)
    async def modify_post(self, interaction: discord.Interaction, message: discord.Message) -> None:
        # If somehow someone runs this without permissions, make sure it gets cancelled.
        if not interaction.permissions.manage_messages:
            embed = discord.Embed(
                description="You do not have permission to use this command.",
                color=0xE02B2B
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        interaction, result = await select_attachment(interaction, message)
        # TODO: stub
        print(result)
        if result is FailureReason:
            # Display ephemeral error message and exit
            return


async def setup(bot) -> None:
    await bot.add_cog(AttachmentTools(bot))

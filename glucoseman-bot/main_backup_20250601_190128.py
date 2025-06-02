import discord
import os
import json
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path
import traceback

# 環境変数の読み込み
load_dotenv()

# ディレクトリ設定
BASE_DIR = Path(__file__).parent
POINTS_FILE = BASE_DIR / "points.json"

# Discordクライアントの設定
intents = discord.Intents.all()  # 全権限を有効化

# または以下の設定も可能です：
# intents = discord.Intents.default()
# intents.message_content = True
# intents.reactions = True
# intents.messages = True
# intents.guilds = True
# intents.guild_messages = True

client = discord.Client(intents=intents)

# サーバーID設定
TARGET_SERVER_ID = 992716525251330058

# サーバー制限チェック
async def is_target_guild(guild_id):
    return guild_id == TARGET_SERVER_ID

# ランキング表示
import json, traceback
from pathlib import Path

POINTS_FILE: Path = BASE_DIR / "points.json"

async def show_ranking(channel, top_n: int = 10):
    """
    ポイントランキングを送信する。
    - ヘッダーは必ず 1 通だけ
    - ファイルなし／データ空ならメッセージを 1 通送って終了
    """
    try:
        # ---------- データ取得 ----------
        if not POINTS_FILE.exists():
            msg = "🏆 **ポイントランキング** 🏆\nまだ誰もポイントを獲得していません🍇"
            await channel.send(msg, delete_after=60)
            return

        with POINTS_FILE.open("r", encoding="utf-8") as f:
            data: dict[str, int] = json.load(f)

        if not data:
            msg = "🏆 **ポイントランキング** 🏆\nまだ誰もポイントを獲得していません🍇"
            await channel.send(msg, delete_after=60)
            return

        # ---------- ランキング生成 ----------
        ranking = sorted(data.items(), key=lambda x: x[1], reverse=True)[:top_n]

        lines = ["🏆 **ポイントランキング** 🏆"]
        for i, (uid, pts) in enumerate(ranking, 1):
            try:
                member = await channel.guild.fetch_member(int(uid))
                name = member.display_name
            except Exception:
                name = f"<@{uid}>"
            lines.append(f"{i}. {name} — {pts} pt")

        await channel.send("\n".join(lines), delete_after=60)

    except Exception:
        traceback.print_exc()
        await channel.send("💥 ランキング取得でエラー発生！ログ確認してな💦", delete_after=30)

# リアクションポイント設定
REACTION_POINTS = {
    "🧃": {"name": "グルコースマン", "points": 1, "type": "info"},
    "🍏": {"name": "さおりんご", "points": 1, "type": "adopt"},
    "🍇": {"name": "ブドウちゃん", "points": 1, "type": "material"}
}

# サーバーIDのチェック
async def check_server(message):
    if message.guild and message.guild.id == TARGET_SERVER_ID:
        return True
    return False

# ユーザーデータの読み書き
async def load_points():
    try:
        with open(POINTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

async def save_points(data):
    with open(POINTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# リアクション追加イベント
@client.event
async def on_reaction_add(reaction, user):
    if user == client.user:
        return

    emoji = str(reaction.emoji)
    if emoji not in REACTION_POINTS:
        return

    # リアクションを付けたユーザーの確認
    reactor = user
    if reactor.bot:  # ボットからのリアクションは無視
        return

    # リアクションを付けられたユーザーの確認
    reacted_user = reaction.message.author
    if reacted_user.bot:  # ボットへのリアクションは無視
        return

    # サーバーIDのチェック
    if not await check_server(reaction.message):
        return

    # ユーザーデータの読み込み
    points_data = await load_points()
    
    # リアクションタイプごとの制限チェック
    reaction_info = REACTION_POINTS[emoji]
    
    # 同じメッセージへの同じタイプのリアクションは1回限り
    reaction_count = 0
    for r in reaction.message.reactions:
        if str(r.emoji) in REACTION_POINTS and REACTION_POINTS[str(r.emoji)]['type'] == reaction_info['type']:
            reaction_count += 1
    if reaction_count > 1:  # 同じタイプのリアクションが既にある場合
        await reaction.message.channel.send(
            f"{reactor.mention} {reaction_info['name']}は既に付いています！\n"
            "同じタイプのリアクションは1回限りです。"
        )
        return

    # リアクションを付けたユーザーがブドウちゃんかさおりんごか確認
    if reaction_info['type'] in ['adopt', 'material']:
        if str(reactor) not in ['ブドウちゃん#0000', 'さおりんご#0000']:
            await reaction.message.channel.send(
                f"{reactor.mention} {reaction_info['name']}はブドウちゃんかさおりんごのみが付けることができます！"
            )
            return

    # ポイントの更新
    user_id = str(reacted_user.id)
    if user_id not in points_data:
        points_data[user_id] = {
            'total_points': 0,
            'weekly_points': 0,
            'info_points': 0,
            'adopt_points': 0,
            'material_points': 0,
            'last_update': datetime.now().isoformat()
        }

    # ポイントの更新
    points_data[user_id]['total_points'] += reaction_info['points']
    points_data[user_id][f"{reaction_info['type']}_points"] += reaction_info['points']
    points_data[user_id]['weekly_points'] += reaction_info['points']
    points_data[user_id]['last_update'] = datetime.now().isoformat()
    
    # データの保存
    await save_points(points_data)
    
    # 確認メッセージを送信
    await reaction.message.channel.send(
        f"{reacted_user.mention} が {reaction_info['name']} を獲得しました！\n"
        f"現在のポイント: {points_data[user_id]['total_points']}pt\n"
        f"（情報提供: {points_data[user_id]['info_points']}pt, "
        f"採用: {points_data[user_id]['adopt_points']}pt, "
        f"素材: {points_data[user_id]['material_points']}pt）"
    )

# リアクション削除イベント
@client.event
async def on_reaction_remove(reaction, user):
    if user == client.user:
        return

    emoji = str(reaction.emoji)
    if emoji not in REACTION_POINTS:
        return

    # リアクションを付けられたユーザーの確認
    reacted_user = reaction.message.author
    if reacted_user.bot:
        return

    # サーバーIDのチェック
    if not await check_server(reaction.message):
        return

    # ユーザーデータの読み込み
    points_data = await load_points()
    user_id = str(reacted_user.id)
    if user_id not in points_data:
        return

    # ポイントの更新
    reaction_info = REACTION_POINTS[emoji]
    points_data[user_id]['total_points'] -= reaction_info['points']
    points_data[user_id][f"{reaction_info['type']}_points"] -= reaction_info['points']
    points_data[user_id]['weekly_points'] -= reaction_info['points']
    points_data[user_id]['last_update'] = datetime.now().isoformat()
    
    # データの保存
    await save_points(points_data)
    
    # 確認メッセージを送信
    await reaction.message.channel.send(
        f"{reacted_user.mention} の {reaction_info['name']} が取り消されました！\n"
        f"現在のポイント: {points_data[user_id]['total_points']}pt"
    )

# ランキング表示コマンド
@client.event
async def on_message(message):
    # クライアント未接続チェック
    if client.user is None:
        return  # ログイン完了前に飛んでくるイベントは無視
    
    # デバッグログ（安全な形式）
    print(f"🔍 {message.content=} | {message.author.id=} | {client.user.id=}")
    print("="*50)
    
    # ボット自身のメッセージは無視
    if message.author.id == client.user.id or message.author.bot:
        return
    
    # サーバー制限チェック
    if message.guild and message.guild.id != TARGET_SERVER_ID:
        return
    
    # コマンド処理
    if message.content.strip().lower() in ('!ランキング', '/rank'):
        print(f"🎯 ランキングコマンド検知！")
        await show_ranking(message.channel)
        return
    
    # デバッグ用：コマンドにマッチしなかった場合
    print(f"🔍 コマンドにマッチしなかった: {message.content}")

    # サーバーIDのチェック
    if not await check_server(message):
        return

    if message.content.startswith('/rank'):
        points_data = await load_points()
        
        # ランキングを計算
        ranking = sorted(
            [(user_id, data['total_points']) 
             for user_id, data in points_data.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]  # 上位10人
        
        # メッセージ作成
        rank_message = "🏆 **ポイントランキング** 🏆\n\n"
        for i, (user_id, points) in enumerate(ranking, 1):
            user = await client.fetch_user(int(user_id))
            rank_message += f"{i}. {user.name} - {points}pt\n"
        
        await message.channel.send(rank_message)

    elif message.content.startswith('/points'):
        # メンションされたユーザーのポイントを表示
        if len(message.mentions) > 0:
            target_user = message.mentions[0]
            user_id = str(target_user.id)
            points_data = await load_points()
            
            if user_id in points_data:
                data = points_data[user_id]
                response = f"{target_user.mention} のポイント:\n"
                response += f"総ポイント: {data['total_points']}pt\n"
                response += f"情報提供: {data['info_points']}pt\n"
                response += f"採用: {data['adopt_points']}pt\n"
                response += f"素材: {data['material_points']}pt"
                await message.channel.send(response)
            else:
                await message.channel.send(f"{target_user.mention} のデータが見つかりません。")

# ボットの起動
@client.event
async def on_ready():
    print(f'ログインしました: {client.user.name}')
    print(f'ID: {client.user.id}')
    print(f'📍 対象サーバー: ヒメタネコミュニティ (ID: {TARGET_SERVER_ID})')
    print('------')

    # サーバーを取得
    target_server = None
    for guild in client.guilds:
        if guild.id == TARGET_SERVER_ID:
            target_server = guild
            break

    if target_server:
        print(f'✅ ターゲットサーバーに接続しました: {target_server.name}')
    else:
        print('❌ ターゲットサーバーに接続できませんでした')

    # サーバーのチャンネルを確認
    if target_server:
        print(f'チャンネル一覧:')
        for channel in target_server.channels:
            if isinstance(channel, discord.TextChannel):
                print(f'  - {channel.name} ({channel.id})')

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
client.run(TOKEN)
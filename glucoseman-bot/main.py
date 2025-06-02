print
import os
import json
import traceback
import discord
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
import asyncio

# ==============================================================================
# 設定
# ==============================================================================
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TARGET_GUILD_ID = 992716525251330058  # ヒメタネコミュニティ
POINTS_FILE = Path(__file__).with_name("points.json")

# ポイントを付与できる権限を持つユーザーのID
AUTHORIZED_REACTION_USERS = [
    568741926829031426,  # ブドウちゃん
    920192804909645834,  # さおりんごさん
]

# リアクションポイント設定
REACTION_POINTS = {
    "<:glucose_man:1360489607010975975>": {"name": "グルコースマン", "points": 1},
    "<:saoringo:1378640284358938685>": {"name": "さおりんご", "points": 1},
    "<:budouchan:1378640247474094180>": {"name": "ブドウちゃん", "points": 3},
}

# Intentsの設定
intents = discord.Intents.default()
intents.reactions = True
intents.message_content = True
client = discord.Client(intents=intents)

# 重複防止とレート制限
processed_messages = set()
ranking_lock = asyncio.Lock()  # ランキング処理の同時実行を防ぐ
last_ranking_time = {}  # チャンネルごとの最後のランキング実行時間

# ==============================================================================
# ヘルパー関数
# ==============================================================================
def load_points() -> dict:
    """ポイントデータをファイルから読み込む"""
    try:
        if not POINTS_FILE.exists():
            print("📝 points.jsonが存在しないため、新規作成します")
            return {}
        
        with open(POINTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"📊 ポイントデータ読み込み成功: {len(data)}人のデータ")
        return data
    except json.JSONDecodeError as e:
        print(f"❌ points.jsonの形式が不正です: {e}")
        # バックアップを作成
        if POINTS_FILE.exists():
            backup_name = f"points_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            POINTS_FILE.rename(POINTS_FILE.with_name(backup_name))
            print(f"🔄 破損ファイルを {backup_name} にバックアップしました")
        return {}
    except Exception as e:
        print(f"❌ ポイントデータ読み込みエラー: {e}")
        return {}

def save_points(data: dict) -> None:
    """ポイントデータをファイルに保存する"""
    try:
        with open(POINTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 ポイントデータ保存成功: {len(data)}人のデータ")
    except Exception as e:
        print(f"❌ ポイントデータ保存エラー: {e}")

# ==============================================================================
# イベントハンドラ
# ==============================================================================

@client.event
async def on_ready():
    """Bot起動時に呼ばれる"""
    print(f"✅ Logged in as {client.user} ({client.user.id})")
    guild = client.get_guild(TARGET_GUILD_ID)
    if guild:
        print(f"🎯 ターゲットサーバー {guild.name} ({TARGET_GUILD_ID}) に参加しています！")
    else:
        print(f"⚠️ ターゲットサーバー ID ({TARGET_GUILD_ID}) が見つかりません。")
    
    # 起動時にポイントファイルの状態を確認
    points_data = load_points()
    print(f"📈 現在のポイント保持者: {len(points_data)}人")

@client.event
async def on_message(message: discord.Message):
    """メッセージ受信時に呼ばれる"""
    # Bot自身のメッセージや、クライアントがNoneの場合は無視
    if client.user is None or message.author.id == client.user.id or message.author.bot:
        return

    # ターゲットサーバー以外からのメッセージは無視
    if not message.guild or message.guild.id != TARGET_GUILD_ID:
        return

    # 重複処理を防ぐ
    message_key = f"{message.id}_{message.author.id}_{message.content}"
    if message_key in processed_messages:
        print(f"⚠️ 重複メッセージ検出、スキップ: {message.content[:20]}...")
        return
    processed_messages.add(message_key)

    # メモリリーク防止
    if len(processed_messages) > 1000:
        processed_messages.clear()
        print("🧹 処理済みメッセージリストをクリアしました")

    content = message.content.strip().lower()

    try:
        # !ランキング コマンド
        if content == '!ランキング':
            print(f"🎯 ランキングコマンド検知！ by {message.author.name} (ID: {message.author.id})")
            
            # レート制限チェック（同じチャンネルで5秒以内の連続実行を防ぐ）
            channel_id = message.channel.id
            now = datetime.now()
            if channel_id in last_ranking_time:
                time_diff = (now - last_ranking_time[channel_id]).total_seconds()
                if time_diff < 5:
                    print(f"⏰ ランキングコマンドのレート制限中 ({time_diff:.1f}秒前に実行済み)")
                    await message.channel.send("⏰ ランキング表示は5秒間隔で実行できます。少しお待ちください。")
                    return
            
            last_ranking_time[channel_id] = now
            await show_ranking(message.channel)
            return

        # !ポイント コマンド
        if content == '!ポイント':
            print(f"🎯 ポイント表示コマンド検知！ by {message.author.name}")
            points_data = load_points()
            user_id = str(message.author.id)
            user_points = points_data.get(user_id, {"total_points": 0}).get("total_points", 0)
            await message.channel.send(f"📊 {message.author.mention}さんのポイント: {user_points}ポイント")
            return

        # !デバッグ コマンド（管理者用）
        if content == '!デバッグ' and message.author.id in AUTHORIZED_REACTION_USERS:
            points_data = load_points()
            await message.channel.send(f"🔧 デバッグ情報:\n- ポイント保持者: {len(points_data)}人\n- ファイルサイズ: {POINTS_FILE.stat().st_size if POINTS_FILE.exists() else 0}bytes")
            return

    except Exception as e:
        print(f"❌ コマンド処理でエラー: {e}")
        traceback.print_exc()
        await message.channel.send("⚠️ コマンド処理でエラーが発生しました。")

@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """リアクション追加時に呼ばれる"""
    try:
        if payload.user_id not in AUTHORIZED_REACTION_USERS:
            return
        if payload.guild_id != TARGET_GUILD_ID:
            return

        emoji = str(payload.emoji)
        if emoji not in REACTION_POINTS:
            return

        channel = client.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        message = await channel.fetch_message(payload.message_id)
        
        if message.author.bot or message.author.id == payload.user_id:
            return

        points_data = load_points()
        author_id_str = str(message.author.id)
        
        if author_id_str not in points_data:
            points_data[author_id_str] = {"total_points": 0}

        points_to_add = REACTION_POINTS[emoji]["points"]
        points_data[author_id_str]["total_points"] += points_to_add
        
        save_points(points_data)
        
        reactor_name = f"ID:{payload.user_id}"
        if payload.member:
            reactor_name = payload.member.display_name
        else:
            try:
                reactor_user = await client.fetch_user(payload.user_id)
                reactor_name = reactor_user.name
            except discord.NotFound:
                pass
            
        print(f"✅ {reactor_name} が {message.author.display_name} に {points_to_add} ポイント加算！")

    except Exception as e:
        print(f"❌ リアクション追加処理でエラー: {e}")

@client.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    """リアクション削除時に呼ばれる"""
    try:
        if payload.user_id not in AUTHORIZED_REACTION_USERS:
            return
        if payload.guild_id != TARGET_GUILD_ID:
            return
        
        emoji = str(payload.emoji)
        if emoji not in REACTION_POINTS:
            return

        channel = client.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        message = await channel.fetch_message(payload.message_id)

        if message.author.bot or message.author.id == payload.user_id:
            return

        points_data = load_points()
        author_id_str = str(message.author.id)

        if author_id_str not in points_data:
            return

        points_to_subtract = REACTION_POINTS[emoji]["points"]
        if "total_points" in points_data[author_id_str]:
            points_data[author_id_str]["total_points"] -= points_to_subtract
            if points_data[author_id_str]["total_points"] < 0:
                points_data[author_id_str]["total_points"] = 0
            
            save_points(points_data)
            print(f"✅ リアクション取り消し: {points_to_subtract} ポイント減算")

    except Exception as e:
        print(f"❌ リアクション削除処理でエラー: {e}")

async def show_ranking(channel: discord.TextChannel, top_n: int = 10):
    """ランキングを表示する関数"""
    async with ranking_lock:  # 同時実行を防ぐ
        try:
            print("🔍 === ランキング表示処理開始 ===")
            
            # ポイントデータ読み込み
            points_data = load_points()
            print(f"📊 読み込み完了: {len(points_data)}人のデータ")
            
            if not points_data:
                message = "🏆 **ポイントランキング** 🏆\nまだ誰もポイントを獲得していません🍇"
                await channel.send(message)
                print("📝 ランキング送信完了（データなし）")
                return

            # 有効なユーザーを抽出
            valid_users_points = {}
            for uid, data in points_data.items():
                if isinstance(data, dict):
                    points = data.get("total_points", 0)
                    if points > 0:
                        valid_users_points[uid] = points
                        print(f"  📈 {uid}: {points}pt")

            print(f"🎯 有効ユーザー: {len(valid_users_points)}人")

            if not valid_users_points:
                message = "🏆 **ポイントランキング** 🏆\nまだ誰もポイントを獲得していません🍇"
                await channel.send(message)
                print("📝 ランキング送信完了（有効データなし）")
                return
                
            # ソート
            sorted_users_ids = sorted(
                valid_users_points.keys(),
                key=lambda user_id: valid_users_points[user_id],
                reverse=True
            )
            print(f"🔄 ソート完了: {len(sorted_users_ids)}人")

            # メッセージ作成
            lines = ["🏆 **ポイントランキング** 🏆"]
            
            for i, user_id_str in enumerate(sorted_users_ids[:top_n]):
                user_id = int(user_id_str)
                try:
                    member = await channel.guild.fetch_member(user_id)
                    name = member.display_name
                except discord.NotFound:
                    try:
                        user_obj = await client.fetch_user(user_id)
                        name = f"{user_obj.name} (元メンバー)"
                    except discord.NotFound:
                        name = f"不明なユーザー <@{user_id_str}>"
                
                points = valid_users_points[user_id_str]
                lines.append(f"{i + 1}. {name} — {points} pt")
                print(f"  📋 {i + 1}位: {name} ({points}pt)")

            ranking_message = "\n".join(lines)
            print(f"📤 メッセージ送信中... (文字数: {len(ranking_message)})")
            
            await channel.send(ranking_message)
            print(f"✅ === ランキング送信完了（{len(lines)-1}名） ===")
            
        except Exception as e:
            print(f"❌ === ランキング表示でエラー ===")
            print(f"エラー詳細: {e}")
            traceback.print_exc()
            print("==========================================")

# ==============================================================================
# Botを実行
# ==============================================================================
if TOKEN:
    print("🚀 Bot起動中...")
    client.run(TOKEN)
else:
    print("❌ DISCORD_BOT_TOKENが設定されていません。")
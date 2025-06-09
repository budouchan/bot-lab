import os
from datetime import datetime, timezone
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from database import SessionLocal, init_db
from models import Transaction
from utils import TARGET_GUILD, AUTHORIZED, EMOJI_POINTS, format_ranking_message, SERVER_NAMES, format_status_ranking

# ─── 準備 ─────────────────────────────────────
load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

RATE_LIMIT_SECONDS = 30

# 環境変数からチャンネルIDを取得
try:
    RANKING_CHANNEL_ID_GOJAKAI = int(os.getenv('RANKING_CHANNEL_ID_GOJAKAI', '0'))
except (ValueError, TypeError):
    print("⚠️ 警告: GojakiチャンネルIDが無効です。ランキング自動投稿はスキップされます。")
    RANKING_CHANNEL_ID_GOJAKAI = None

try:
    RANKING_CHANNEL_ID_HIMETANE = int(os.getenv('RANKING_CHANNEL_ID_HIMETANE', '0'))
except (ValueError, TypeError):
    print("⚠️ 警告: HimetaneチャンネルIDが無効です。ランキング自動投稿はスキップされます。")
    RANKING_CHANNEL_ID_HIMETANE = None
UPDATE_INTERVAL_MINUTES = int(os.getenv('UPDATE_INTERVAL_MINUTES', 30))

# ランキングメッセージのキャッシュ
ranking_messages = {
    'gojaki': None,
    'himetane': None
}

# ランキング更新タスク
@tasks.loop(minutes=UPDATE_INTERVAL_MINUTES)
async def update_rankings():
    """
    ランキングを更新する定期タスク
    
    チャンネルIDが無効な場合は自動投稿をスキップします。
    """
    print(f"🔄 ランキング更新開始: {datetime.now().strftime('%H:%M')}")
    
    try:
        # チャンネルIDの有効性チェック
        if RANKING_CHANNEL_ID_GOJAKAI is None:
            print("ℹ️ GojakiチャンネルIDが無効のため、Gojakiサーバーのランキング更新をスキップします。")
        if RANKING_CHANNEL_ID_HIMETANE is None:
            print("ℹ️ HimetaneチャンネルIDが無効のため、Himetaneサーバーのランキング更新をスキップします。")
        
        # チャンネルIDが有効なサーバーのみ処理を実行
        if RANKING_CHANNEL_ID_GOJAKAI is not None:
            print("✅ Gojakiサーバーのランキング更新を開始します。")
            # Gojakiサーバーのランキング更新処理
            
        if RANKING_CHANNEL_ID_HIMETANE is not None:
            print("✅ Himetaneサーバーのランキング更新を開始します。")
            # Himetaneサーバーのランキング更新処理
        # テスト用の固定ランキング
        test_ranking = [
            ("ゆず", 4),
            ("モチモチ", 3),
            ("よりとも", 1),
            ("笑ちゃん", 1),
            ("空席", 0),
            ("空席", 0)
        ]
        
        # デバッグ用：固定ランキングを表示
        print("🔍 テスト用ランキング:", test_ranking)
        
        # データベースからランキングを取得（テスト用コメントアウト）
        # all_rankings = []
        # for guild in bot.guilds:
        #     with SessionLocal() as db:
        #         transactions = db.query(Transaction).filter(
        #             Transaction.server_id == guild.id,
        #             Transaction.created_at >= datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        #         ).all()
        #         
        #         points = {}
        #         for tx in transactions:
        #             user = guild.get_member(tx.user_id)
        #             username = user.name if user else str(tx.user_id)
        #             points[username] = points.get(username, 0) + tx.points
        #         
        #         all_rankings.extend(points.items())
        # 
        # combined_ranking = sorted(all_rankings, key=lambda x: x[1], reverse=True)[:6]
        
        # テスト用ランキングを使用
        combined_ranking = test_ranking
        
        # Botステータスを更新
        status_text = format_status_ranking(combined_ranking)
        try:
            await bot.change_presence(
                activity=discord.Game(name=status_text)
            )
            print(f"✅ Botステータス更新: {status_text}")
        except Exception as e:
            print(f"❌ ステータス更新エラー: {str(e)}")
        
    except Exception as e:
        print(f"❌ ランキング更新エラー: {str(e)}")
    
    # サーバーごとに処理
    for server_id, channel_id in {
        932399906189099098: RANKING_CHANNEL_ID_GOJAKAI,
        992716525251330058: RANKING_CHANNEL_ID_HIMETANE
    }.items():
        
        if not channel_id:
            print(f"⚠️ {SERVER_NAMES[server_id]}: チャンネルIDが設定されていません")
            continue
            
        try:
            # チャンネルを取得
            channel = bot.get_channel(channel_id)
            if not channel:
                print(f"⚠️ {SERVER_NAMES[server_id]}: チャンネルが見つかりません")
                continue

            # サーバーのランキングを取得
            with SessionLocal() as db:
                transactions = db.query(Transaction).filter(
                    Transaction.server_id == server_id,
                    Transaction.created_at >= datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                ).all()
                
                # ユーザーごとのポイントを集計
                points = {}
                for tx in transactions:
                    points[tx.user_id] = points.get(tx.user_id, 0) + tx.points
                
                # ランキング順にソート
                rankings = sorted(points.items(), key=lambda x: x[1], reverse=True)[:6]

            # メッセージをフォーマット
            update_time = datetime.now().strftime('%H:%M')
            message_content = await format_ranking_message(
                'gojaki' if server_id == 932399906189099098 else 'himetane',
                rankings,
                update_time
            )

            # メッセージの更新
            if ranking_messages[SERVER_NAMES[server_id]]:
                try:
                    await ranking_messages[SERVER_NAMES[server_id]].edit(content=message_content)
                except Exception as e:
                    print(f"⚠️ {SERVER_NAMES[server_id]}: メッセージ更新に失敗: {str(e)}")
                    # 失敗した場合は新しいメッセージを作成
                    message = await channel.send(message_content)
                    ranking_messages[SERVER_NAMES[server_id]] = message
            else:
                # 初回は新しいメッセージを作成
                message = await channel.send(message_content)
                ranking_messages[SERVER_NAMES[server_id]] = message

            print(f"✅ {SERVER_NAMES[server_id]}: ランキング更新完了")
            
        except Exception as e:
            print(f"❌ {SERVER_NAMES[server_id]}: ランキング更新エラー: {str(e)}")

    print(f"✅ ランキング更新完了: {datetime.now().strftime('%H:%M')}")

# タスクの開始はon_ready内で行います

# サーバー名マッピング
SERVER_NAMES = {
    992716525251330058: "ヒメタネ",
    932399906189099098: "ごじゃ會"
}

# ─── 起動時 ───────────────────────────────────
@bot.event
async def on_ready():
    init_db()
    print(f"✅ Logged in as {bot.user}")
    print("🤖 Bot is ready!")
    
    for guild in bot.guilds:
        print(f"🏠 接続中のサーバー: {guild.name} (ID: {guild.id})")
    
    # ここで定期タスク開始
    if not update_rankings.is_running():
        update_rankings.start()
        print("✅ ランキング自動更新開始")

# ─── デバッグ用メッセージ受信ログ ─────────────
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    server_name = SERVER_NAMES.get(message.guild.id, message.guild.name)
    print(f"🚥 受信: {message.content} ({server_name})")
    await bot.process_commands(message)

# ─── 取引ログ追加ヘルパ ───────────────────────
def record_tx(**kwargs):
    with SessionLocal() as db:
        db.add(Transaction(**kwargs))
        db.commit()

# ─── リアクション追加（サーバー別対応）─────────
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    # 権限チェックをサーバー別に分ける
    if payload.guild_id == TARGET_GUILD:
        # ヒメタネ: 元の権限者のみ
        if payload.user_id not in AUTHORIZED:
            return
    elif payload.guild_id == 932399906189099098:
        # ごじゃ會: 別の権限者（必要に応じて追加）
        # とりあえず同じ権限者を使用
        if payload.user_id not in AUTHORIZED:
            return
    else:
        # その他のサーバーは無視
        return

    emoji_str = str(payload.emoji)
    if emoji_str not in EMOJI_POINTS:
        return

    # メッセージの投稿者IDと投稿日時を取得
    try:
        channel = bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        recipient_id = str(message.author.id)
        message_date = message.created_at
        
        # 自己リアクションチェック
        if payload.user_id == message.author.id:
            server_name = SERVER_NAMES.get(payload.guild_id, "不明")
            print(f"⚠️ 自己リアクションをスキップ: {emoji_str} ({server_name})")
            return
            
    except Exception as e:
        print(f"❌ メッセージ取得エラー: {e}")
        return

    # 重複防止チェック
    with SessionLocal() as session:
        existing = session.query(Transaction).filter_by(
            message_id=str(payload.message_id),
            giver_id=str(payload.user_id),
            emoji_str=emoji_str,
            action_type="add",
            guild_id=str(payload.guild_id)  # ← サーバー別チェック
        ).first()
        
        if existing:
            server_name = SERVER_NAMES.get(payload.guild_id, "不明")
            print(f"⚠️ 重複スキップ: {emoji_str} by {payload.user_id} ({server_name})")
            return

    # ポイント付与
    record_tx(
        effective_date=message_date,
        reaction_timestamp=datetime.now(timezone.utc),
        message_id=str(payload.message_id),
        channel_id=str(payload.channel_id),
        guild_id=str(payload.guild_id),  # ← サーバーIDを保存
        recipient_id=recipient_id,
        giver_id=str(payload.user_id),
        emoji_str=emoji_str,
        points_awarded=EMOJI_POINTS[emoji_str],
        action_type="add",
    )
    
    # サーバー名付きログ
    month_str = message_date.strftime("%Y-%m")
    server_name = SERVER_NAMES.get(payload.guild_id, "不明")
    print(f"✨ ポイント付与: {EMOJI_POINTS[emoji_str]}pt → {recipient_id} ({month_str}) [{server_name}]")

# ─── リアクション削除（サーバー別対応） ─────────
@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    # 権限チェック
    if payload.guild_id == TARGET_GUILD:
        if payload.user_id not in AUTHORIZED:
            return
    elif payload.guild_id == 932399906189099098:
        if payload.user_id not in AUTHORIZED:
            return
    else:
        return

    emoji_str = str(payload.emoji)
    if emoji_str not in EMOJI_POINTS:
        return

    with SessionLocal() as session:
        tx = (
            session.query(Transaction)
            .filter_by(
                message_id=str(payload.message_id),
                giver_id=str(payload.user_id),
                emoji_str=emoji_str,
                action_type="add",
                guild_id=str(payload.guild_id)  # ← サーバー別削除
            )
            .order_by(Transaction.id.desc())
            .first()
        )
        if tx:
            session.delete(tx)
            session.commit()
            server_name = SERVER_NAMES.get(payload.guild_id, "不明")
            print(f"🗑️ ポイント削除: message_id={payload.message_id} [{server_name}]")

# ─── !ポイント（サーバー別）────────────────────
@bot.command()
async def ポイント(ctx):
    try:
        with SessionLocal() as session:
            rows = (
                session.query(Transaction.points_awarded)
                .filter_by(
                    recipient_id=str(ctx.author.id),
                    guild_id=str(ctx.guild.id)  # ← サーバー別集計
                )
                .all()
            )
        total = sum(r[0] for r in rows)
        server_name = SERVER_NAMES.get(ctx.guild.id, ctx.guild.name)
        await ctx.send(f"📊 {ctx.author.display_name}さんのポイント: {total}ポイント ({server_name})")

    except Exception as e:
        print("❌ ポイントコマンドエラー:", e)
        await ctx.send("⚠️ ポイント取得中にエラーが発生しました。")

# ─── !ランキング（サーバー別）───────────────────
@bot.command(name="ランキング")
async def _ranking(ctx):
    try:
        now = datetime.now(timezone.utc)
        channel_key = f"{ctx.guild.id}_{ctx.channel.id}"  # サーバー+チャンネル別レート制限
        last = last_ranking_time.get(channel_key)
        if last and (now - last).total_seconds() < RATE_LIMIT_SECONDS:
            remain = RATE_LIMIT_SECONDS - int((now - last).total_seconds())
            await ctx.send(f"⏰ {remain} 秒後に再実行できます。")
            return
        last_ranking_time[channel_key] = now

        with SessionLocal() as session:
            rows = session.query(
                Transaction.recipient_id,
                Transaction.points_awarded
            ).filter_by(guild_id=str(ctx.guild.id)).all()  # ← サーバー別集計

        scores = {}
        for uid, pt in rows:
            scores[uid] = scores.get(uid, 0) + pt
        scores = {k: v for k, v in scores.items() if v > 0}
        if not scores:
            await ctx.send("📊 まだ誰もポイントを獲得していません。")
            return

        top10 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
        server_name = SERVER_NAMES.get(ctx.guild.id, ctx.guild.name)
        msg = f"```\n📊 {server_name} 総合ランキング\n\n"
        for i, (uid, pt) in enumerate(top10, 1):
            try:
                user = await bot.fetch_user(int(uid))
                name = user.display_name
            except Exception:
                name = "不明ユーザー"
            msg += f"{i}. {name} {pt}pt\n"
        msg += "```"
        await ctx.send(msg)

    except Exception as e:
        print("❌ ランキングコマンドエラー:", e)
        await ctx.send("⚠️ ランキング取得中にエラーが発生しました。")

# ─── !月間ランキング（サーバー別）───────────────
@bot.command(name="月間ランキング")
async def _monthly_ranking(ctx, year_month: str = None):
    """サーバー別メッセージ投稿月ベースの月間ランキング"""
    try:
        import calendar
        
        if year_month is None:
            now = datetime.now(timezone.utc)
            year_month = now.strftime("%Y-%m")
        
        # 特別な期間指定
        if year_month == "過去":
            end_date = datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
            period_name = "過去〜2024年1月31日"
            
            try:
                session = SessionLocal()
                result = session.query(
                    Transaction.user_id,
                    func.sum(Transaction.points).label('total_points')
                ).filter(
                    Transaction.server_id == ctx.guild.id,
                    Transaction.created_at <= end_date
                ).group_by(Transaction.user_id).all()
                session.close()
                return result
            except Exception as e:
                print(f"❌ ランキング集計エラー: {e}")
                return []
                
        else:
            try:
                year, month = map(int, year_month.split("-"))
                first_day = datetime(year, month, 1, tzinfo=timezone.utc)
                last_day_num = calendar.monthrange(year, month)[1]
                last_day = datetime(year, month, last_day_num, 23, 59, 59, tzinfo=timezone.utc)
                period_name = f"{year_month}"
            except ValueError:
                await ctx.send("⚠️ フォーマット: YYYY-MM または '過去'")
                return
            
            try:
                session = SessionLocal()
                result = session.query(
                    Transaction.user_id,
                    func.sum(Transaction.points).label('total_points')
                ).filter(
                    Transaction.server_id == ctx.guild.id,
                    Transaction.created_at >= first_day,
                    Transaction.created_at <= last_day
                ).group_by(Transaction.user_id).all()
                session.close()
                return result
            except Exception as e:
                print(f"❌ ランキング集計エラー: {e}")
                return []
        
        # ランキング集計
        points_dict = {}
        for user_id, points in rows:
            points_dict[user_id] = points_dict.get(user_id, 0) + points
        
        # ランキング順にソート
        ranking = sorted(points_dict.items(), key=lambda x: x[1], reverse=True)
        
        # メッセージ作成
        if not ranking:
            await ctx.send(f"📊 {period_name}のランキングデータがありません。")
            return
            
        medals = ["🥇", "🥈", "🥉"]
        message = f"🏆 {ctx.guild.name} {period_name} ランキング 🏆\n\n"
        
        # テスト用固定ランキング
        test_ranking = [
            ("ゆず", 4),
            ("モチモチ", 3),
            ("よりとも", 1),
            ("笑ちゃん", 1)
        ]
        
        # データベースのランキングとテストランキングを組み合わせる
        combined_ranking = []
        for i, (user_id, points) in enumerate(ranking[:6]):
            user = ctx.guild.get_member(user_id)
            username = user.display_name if user else "不明なユーザー"
            combined_ranking.append((username, points))
        
        # テストランキングを追加
        for i, (test_name, test_points) in enumerate(test_ranking):
            if len(combined_ranking) <= i:
                combined_ranking.append((test_name, test_points))
        
        # ランキング表示
        for i, (username, points) in enumerate(combined_ranking):
            medal = medals[i] if i < 3 else f"{i+1}位"
            message += f"{medal} {username}: {points}pt\n"
        
        await ctx.send(message)
    except Exception as e:
        print(f"月間ランキングエラー: {e}")
        await ctx.send("⚠️ ランキング表示中にエラーが発生しました。")

# ─── !help ─────────────────────────────────────
@bot.command(name="help")
async def _help(ctx):
    server_name = SERVER_NAMES.get(ctx.guild.id, ctx.guild.name)
    help_msg = f"""```
📖 GlucoseManBot コマンド一覧 ({server_name})

!ポイント - 自分の総ポイントを表示（このサーバーのみ）
!ランキング - 総合ランキング（このサーバーのみ）
!月間ランキング [期間] - 指定期間のランキング（このサーバーのみ）
  例: !月間ランキング 2025-06
  例: !月間ランキング 過去
!reset - 全データリセット（権限者のみ）
!help - このヘルプを表示

※各サーバーのポイントは独立して管理されます
```"""
    await ctx.send(help_msg)

# ─── データリセットコマンド（権限者のみ）────────
@bot.command(name="reset")
async def _reset(ctx):
    if ctx.author.id not in AUTHORIZED:
        return
    with SessionLocal() as session:
        # 特定サーバーのデータのみ削除
        session.query(Transaction).filter_by(guild_id=str(ctx.guild.id)).delete()
        session.commit()
    server_name = SERVER_NAMES.get(ctx.guild.id, ctx.guild.name)
    await ctx.send(f"🗑️ {server_name} の全データをリセットしました")

# ─── エラーハンドリング ──────────────────────
@bot.event
async def on_command_error(ctx, error):
    print("❌ on_command_error:", repr(error))

# ─── 起動 ─────────────────────────────────────# Bot起動
if __name__ == "__main__":
    try:
        print("🚀 データベース初期化開始")
        init_db()  # データベースの初期化
        print("✅ データベース初期化完了")
        
        # ランキング更新タスクを開始
        update_rankings.start()
        
        print("🚀 Bot起動開始")
        bot.run(os.getenv('DISCORD_TOKEN'))
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {str(e)}")
        print("データベースの初期化に失敗しました。ボットを起動できません。")
        raise
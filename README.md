# ai-guard — AIに長い仕事を任せるための、AIの外に置く部品

Claude Code などのAIエージェントに、何週間・何ヶ月という長い開発や分析を任せるときに、AIの「外」に置いておく小さな部品の一式です。

- **memguard.py / capped** — 計算にメモリの上限をかける。上限がなければ起動しない。想定を超えたら待たずに止める
- **safe_find.py** — フォルダの「輪」(自分の親を指すシンボリックリンク)で暴走しないファイル探索。輪を作らない近道づくり
- **hooks/block_dangerous.py + install_hook.py** — Claude Code のフックで、取り返しのつかないコマンド(`rm -rf`、`git reset --hard` など)を実行の直前に止める
- **holdout_guard.py** — 答え合わせ用のデータを、条件を探す・選ぶ段階で使わせない。開いた回数を記録し、使い切ったら開けない
- **extract_user_messages.py** — Claude Code の会話の記録から、人間の発言だけを取り出す(会話が切れて再開するとき用)
- **prompts/** — 別のモデルに監査させる、記録を外から読ませる、規則を棚卸しする、などの指示文
- **07_点検表.md** — 長期運用の点検表
- **short_test/** — 自分の環境で「短い試験」を繰り返す台本
- **tests/test_all.py** — 部品の動作確認

## 動く環境

- Linux、または Windows 11 の WSL2(Ubuntu)。Python 3(標準ライブラリだけ)
- 作者の環境で、Linux と Windows 11 + WSL2 の両方で、テスト48項目すべて合格しています
- メモリの上限(memguard の一部、capped)は、systemd と cgroup v2 が使える環境が必要です。macOS と、WSL を使わない Windows では使えません

## 安全のために

- どの部品も、**外部と通信しません**。標準ライブラリだけを使い、短く、全文を読める長さにしています
- 他人が作ったプログラムを入れる前には、中身を確かめてください。コードを読めない場合は、ファイルの中身をふだん使っているAIに見せて、「インターネットと通信する処理はあるか」「このフォルダの外のファイルを消したり書き換えたりする処理はあるか」「パスワードや秘密の情報を読み取る処理はあるか」を確かめてもらってください
- フックや拒否の設定は「網」であって「壁」ではありません。書き方次第ですり抜けられます

## 入れ方(Ubuntu の画面で)

リリースのページから `ai-guard-<版>.tar.gz` をダウンロードし、展開して、テストを流します。

```
cd ~
curl -L -o ai-guard.tar.gz https://github.com/miokuri-ai/ai-guard/releases/download/v1.0.0/ai-guard-1.0.0.tar.gz
sha256sum ai-guard.tar.gz
tar xzf ai-guard.tar.gz
python3 ~/ai-guard/tests/test_all.py
```

`sha256sum` で表示される文字列が、リリースのページに書かれた指紋と同じであることを確かめてから展開してください。最後に `結果: OK 48 / NG 0` と出れば完了です。

## 使い方

使い方(なぜその部品が要るのか、Claude Code にどう守らせるか、効いているかの確かめ方、初心者向けの準備の手順)は、作者の note の手引きにまとめています。

- 手引き: https://note.com/miokuri_ai/n/n4a01438ebd90
- 無料の連載「AIに長い仕事を任せたら」(第1回): https://note.com/miokuri_ai/n/nefa1bd997b0f

## 利用条件

MIT ライセンスです(LICENSE を参照)。自由に使い、直し、配ってかまいません。作者は、この部品を使った結果について責任を負いません。

作者: 見送りの人

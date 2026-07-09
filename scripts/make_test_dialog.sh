#!/usr/bin/env bash
# Quick 2-speaker Russian dialog for ASR/diarization smoke-testing (Phase 2).
# macOS has one RU voice (Milena), so the "client" is that voice pitch-shifted down —
# acoustically distinct, which is what the diarizer needs to separate.
# Proper test data (edge-tts neural voices, 8 kHz telephone, WER refs) lands in Phase 5.
set -euo pipefail

OUT_DIR="${1:-test_data}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT_DIR"

say_line() {  # $1=index $2=text
  say -v Milena -o "$WORK/$1.aiff" "$2"
  ffmpeg -y -loglevel error -i "$WORK/$1.aiff" -ar 16000 -ac 1 "$WORK/$1.wav"
}

pitch_down() {  # $1=index — lower pitch, keep tempo => a different-sounding speaker
  ffmpeg -y -loglevel error -i "$WORK/$1.wav" \
    -af "asetrate=16000*0.82,aresample=16000,atempo=1.2195" "$WORK/$1_c.wav"
  mv "$WORK/$1_c.wav" "$WORK/$1.wav"
}

# Operator = even indices, Client = odd indices
say_line 0 "Добрый день! Контакт-центр МТБанка, меня зовут Анна. Чем могу помочь?"
say_line 1 "Здравствуйте. Я хотел бы узнать про кредит наличными, какие у вас условия?"
say_line 2 "Конечно, подскажу. Уточните, пожалуйста, желаемую сумму и срок кредита."
say_line 3 "Мне нужно примерно десять тысяч рублей на два года."
say_line 4 "Хорошо. Ставка составит от восемнадцати процентов годовых. Обращаю внимание, что окончательное решение принимает банк."
say_line 5 "Понятно. А можно оформить онлайн, без визита в отделение?"
say_line 6 "Да, заявку можно подать в мобильном приложении. Я отправлю вам подробные условия на электронную почту."
say_line 7 "Отлично, спасибо большое. До свидания."
say_line 8 "Спасибо за обращение в МТБанк. Хорошего дня!"

for i in 1 3 5 7; do pitch_down "$i"; done

# 0.4 s silence between turns
ffmpeg -y -loglevel error -f lavfi -t 0.4 -i anullsrc=r=16000:cl=mono "$WORK/sil.wav"

: > "$WORK/list.txt"
for i in 0 1 2 3 4 5 6 7 8; do
  echo "file '$WORK/$i.wav'" >> "$WORK/list.txt"
  echo "file '$WORK/sil.wav'" >> "$WORK/list.txt"
done

ffmpeg -y -loglevel error -f concat -safe 0 -i "$WORK/list.txt" -ar 16000 -ac 1 "$OUT_DIR/call_dialog.wav"
ffmpeg -y -loglevel error -i "$OUT_DIR/call_dialog.wav" -ar 16000 -b:a 64k "$OUT_DIR/call_dialog.mp3"

echo "Wrote:"
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT_DIR/call_dialog.wav" | sed 's/^/  wav /'
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT_DIR/call_dialog.mp3" | sed 's/^/  mp3 /'

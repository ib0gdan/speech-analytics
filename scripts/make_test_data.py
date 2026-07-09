"""Generate the RU test corpus (DATA-01).

Two distinct neural voices via edge-tts (as the task suggests): a female operator and a male
client. Each call is written as a list of turns; the turn TEXT is also the reference transcript,
so the WER ground truth is exact by construction.

Coverage the task asks for: >=5 files, >=1 telephone-grade 8 kHz, >=1 two-speaker dialog over a
minute, >=5 minutes total, and a spread of formats (wav / mp3 / ogg) and sample rates.

Run inside the helper container (see scripts/make_test_data.sh).
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import edge_tts

OPERATOR_VOICE = "ru-RU-SvetlanaNeural"   # оператор — женский голос
CLIENT_VOICE = "ru-RU-DmitryNeural"       # клиент — мужской голос

OUT = Path("/work/test_data")
TMP = Path("/tmp/tts")

OP, CL = "Оператор", "Клиент"

# (filename, container-format args, [(speaker, text), ...])
CALLS: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "call_credit_consultation", "wav16",
        [
            (OP, "Добрый день! Контакт-центр МТБанка, меня зовут Анна. Чем могу помочь?"),
            (CL, "Здравствуйте. Я хотел бы узнать про кредит наличными. Какие у вас условия?"),
            (OP, "Конечно, расскажу. Уточните, пожалуйста, желаемую сумму и срок кредита."),
            (CL, "Мне нужно примерно пятнадцать тысяч рублей на два года."),
            (OP, "Хорошо. Ставка составит от восемнадцати процентов годовых. "
                 "Обращаю внимание, что окончательное решение принимает банк."),
            (CL, "А есть какие-то скрытые комиссии за обслуживание?"),
            (OP, "Нет, комиссии за обслуживание кредита у нас отсутствуют. "
                 "Вы платите только проценты по договору."),
            (CL, "Понятно. А можно оформить онлайн, без визита в отделение?"),
            (OP, "Да, заявку можно подать в мобильном приложении. "
                 "Потребуется паспорт и справка о доходах."),
            (CL, "Справку обязательно нести? У меня зарплатная карта вашего банка."),
            (OP, "Если вы зарплатный клиент, справка не нужна. Мы видим ваш доход."),
            (CL, "Отлично. Пришлите мне подробные условия, пожалуйста."),
            (OP, "Я отправлю вам подробные условия на электронную почту в течение часа."),
            (CL, "Спасибо большое. До свидания."),
            (OP, "Спасибо за обращение в МТБанк. Хорошего дня!"),
        ],
    ),
    (
        "call_card_blocked", "mp3",
        [
            (OP, "Контакт-центр МТБанка, оператор Мария. Слушаю вас."),
            (CL, "Здравствуйте. У меня заблокировали карту, я не могу расплатиться в магазине."),
            (OP, "Понимаю ваше беспокойство. Назовите, пожалуйста, последние четыре цифры карты."),
            (CL, "Четыре, семь, два, девять."),
            (OP, "Спасибо. Вижу, карта заблокирована системой защиты после подозрительной операции."),
            (CL, "Какая ещё подозрительная операция? Я ничего не делал!"),
            (OP, "Вчера в двадцать три часа была попытка оплаты в интернете на крупную сумму. "
                 "Вы её совершали?"),
            (CL, "Нет, точно не я. Это мошенники."),
            (OP, "Тогда мы оставляем карту заблокированной и перевыпускаем её. "
                 "Средства на счёте в безопасности."),
            (CL, "А сколько ждать новую карту?"),
            (OP, "Перевыпуск занимает до пяти рабочих дней. Заявление я оформлю прямо сейчас."),
            (CL, "Хорошо, оформляйте. И проверьте, пожалуйста, не было ли других списаний."),
            (OP, "Проверила, других операций нет. Заявление принято, номер обращения придёт в смс."),
            (CL, "Спасибо, до свидания."),
            (OP, "Всего доброго!"),
        ],
    ),
    (
        "call_transfer_issue", "phone8k",     # telephone grade: 8 kHz mu-law
        [
            (OP, "МТБанк, оператор Ольга. Здравствуйте."),
            (CL, "Добрый день. Я вчера отправил перевод, а деньги не дошли получателю."),
            (OP, "Уточните, пожалуйста, сумму перевода и время отправки."),
            (CL, "Двести рублей, вчера около шести вечера."),
            (OP, "Вижу операцию. Перевод находится в обработке банка получателя."),
            (CL, "И сколько это будет длиться?"),
            (OP, "Обычно до трёх рабочих дней. Если деньги не поступят, мы направим запрос."),
            (CL, "А комиссию вернут, если перевод не пройдёт?"),
            (OP, "Да, при отмене перевода комиссия возвращается в полном объёме."),
            (CL, "Понял вас, спасибо. Подожду."),
            (OP, "Спасибо за обращение. Хорошего дня!"),
        ],
    ),
    (
        "call_complaint_escalation", "ogg",
        [
            (CL, "Это уже третий раз, когда я звоню! Мне никто не перезванивает!"),
            (OP, "Приношу извинения за неудобства. Меня зовут Ирина, я разберусь в ситуации."),
            (CL, "Мне обещали перезвонить два дня назад по вопросу возврата средств."),
            (OP, "Вижу ваше обращение. Оно действительно не было обработано в срок."),
            (CL, "И что мне теперь делать? Я потерял время и деньги."),
            (OP, "Я передаю обращение на контроль руководителю и фиксирую жалобу."),
            (CL, "Мне нужен конкретный срок, а не общие слова."),
            (OP, "Ответ будет предоставлен в течение одного рабочего дня. Я лично проконтролирую."),
            (CL, "Надеюсь. Иначе я буду обращаться в Национальный банк."),
            (OP, "Понимаю вас. Ещё раз извините за задержку. Мы обязательно свяжемся с вами."),
        ],
    ),
    (
        "call_deposit_info", "mp3",
        [
            (OP, "Здравствуйте, МТБанк, оператор Светлана."),
            (CL, "Добрый день. Подскажите, какие сейчас ставки по вкладам?"),
            (OP, "По срочному вкладу на год ставка составляет одиннадцать процентов годовых."),
            (CL, "А если снять деньги раньше срока?"),
            (OP, "При досрочном снятии проценты пересчитываются по ставке до востребования."),
            (CL, "Ясно. Спасибо за информацию."),
            (OP, "Пожалуйста. Обращайтесь. Всего доброго!"),
        ],
    ),
]

VOICE = {OP: OPERATOR_VOICE, CL: CLIENT_VOICE}


def sh(*args: str) -> None:
    subprocess.run(args, check=True, capture_output=True)


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip() or 0.0)


# edge-tts streams the audio; a network hiccup makes `save()` write a TRUNCATED file without
# raising. That silently corrupted a turn once (a whole client question vanished from the
# corpus and only surfaced as an inexplicable WER spike). So: verify, and retry.
_MIN_SEC_PER_WORD = 0.15
_MAX_ATTEMPTS = 4


async def synth_turn(text: str, voice: str, dest: Path) -> None:
    expected = _MIN_SEC_PER_WORD * len(text.split())
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        await edge_tts.Communicate(text, voice).save(str(dest))
        got = duration(dest)
        if got >= expected:
            return
        print(f"    ! truncated synthesis ({got:.1f}s < {expected:.1f}s), retry {attempt}")
    raise RuntimeError(f"edge-tts kept truncating: {text[:50]!r}")


async def build_call(name: str, fmt: str, turns: list[tuple[str, str]]) -> None:
    work = TMP / name
    work.mkdir(parents=True, exist_ok=True)

    parts: list[Path] = []
    for i, (speaker, text) in enumerate(turns):
        raw = work / f"{i}.mp3"
        await synth_turn(text, VOICE[speaker], raw)
        wav = work / f"{i}.wav"
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-ar", "16000", "-ac", "1", str(wav))
        parts.append(wav)

    silence = work / "sil.wav"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-t", "0.45",
       "-i", "anullsrc=r=16000:cl=mono", str(silence))

    listing = work / "list.txt"
    listing.write_text("".join(f"file '{p}'\nfile '{silence}'\n" for p in parts))

    merged = work / "merged.wav"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
       "-i", str(listing), "-ar", "16000", "-ac", "1", str(merged))

    OUT.mkdir(parents=True, exist_ok=True)
    if fmt == "wav16":
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", str(merged), str(OUT / f"{name}.wav"))
    elif fmt == "mp3":
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", str(merged), "-b:a", "64k", str(OUT / f"{name}.mp3"))
    elif fmt == "ogg":
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", str(merged), "-c:a", "libvorbis", str(OUT / f"{name}.ogg"))
    elif fmt == "phone8k":
        # Telephone channel: 8 kHz, mu-law — exactly what the task asks to include.
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", str(merged),
           "-ar", "8000", "-acodec", "pcm_mulaw", str(OUT / f"{name}.wav"))

    # Reference transcript: the very text we synthesised.
    (OUT / f"{name}.txt").write_text("\n".join(t for _, t in turns) + "\n", encoding="utf-8")
    print(f"  built {name} ({fmt}, {len(turns)} turns)")


async def main() -> None:
    for name, fmt, turns in CALLS:
        await build_call(name, fmt, turns)


if __name__ == "__main__":
    asyncio.run(main())

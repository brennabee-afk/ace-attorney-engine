from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2
from typing import List, Dict
import os
import random as r
from pydub import AudioSegment
from enum import IntEnum
import ffmpeg
import random
from textwrap import wrap
import spacy
from textblob import TextBlob
from tqdm import tqdm
import string

nlp = spacy.load("en_core_web_sm")
assets_folder = 'D:/Data/ace-attorney-reddit-bot-assets'

codec = cv2.VideoWriter_fourcc(*'MP4V')
extension = 'mp4'
output_codec = 'libx264'


class Location(IntEnum):
    COURTROOM_LEFT = 1
    WITNESS_STAND = 2
    COURTROOM_RIGHT = 3
    CO_COUNCIL = 4
    JUDGE_STAND = 5
    COURT_HOUSE = 6


class Character(IntEnum):
    PHOENIX = 1
    EDGEWORTH = 2
    GODOT = 3
    FRANZISKA = 4
    JUDGE = 5
    LARRY = 6
    MAYA = 7
    KARMA = 8
    PAYNE = 9
    MAGGEY = 10
    PEARL = 11
    LOTTA = 12
    GUMSHOE = 13
    GROSSBERG = 14

    def __str__(self):
        return str(self.name).capitalize()


class Action(IntEnum):
    TEXT = 1
    SHAKE_EFFECT = 2
    OBJECTION = 3
    TEXT_SHAKE_EFFECT = 4


def add_margin(pil_img, top, right, bottom, left):
    width, height = pil_img.size
    new_width = width + right + left
    new_height = height + top + bottom
    result = Image.new(pil_img.mode, (new_width, new_height), (0, 0, 0, 0))
    result.paste(pil_img, (left, top))
    return result


class AnimImg:
    def __init__(
        self,
        path: str,
        *,
        x: int = 0,
        y: int = 0,
        w: int = None,
        h: int = None,
        key_x: int = None,
        key_x_reverse: bool = True,
        shake_effect: bool = False,
        half_speed: bool = False,
        repeat: bool = True,
    ):
        self.x = x
        self.y = y
        self.path = path
        img = Image.open(path, "r")
        if img.format == "GIF" and img.is_animated:
            self.frames = []
            for idx in range(img.n_frames):
                img.seek(idx)
                self.frames.append(self.resize(img, w=w, h=h).convert("RGBA"))
        elif key_x is not None:
            self.frames = []
            for x_pad in range(key_x):
                self.frames.append(
                    add_margin(
                        self.resize(img, w=w, h=h).convert("RGBA"), 0, 0, 0, x_pad
                    )
                )
            if key_x_reverse:
                for x_pad in reversed(range(key_x)):
                    self.frames.append(
                        add_margin(
                            self.resize(img, w=w, h=h).convert("RGBA"), 0, 0, 0, x_pad
                        )
                    )
        else:
            self.frames = [self.resize(img, w=w, h=h).convert("RGBA")]
        self.w = self.frames[0].size[0]
        self.h = self.frames[0].size[1]
        self.shake_effect = shake_effect
        self.half_speed = half_speed
        self.repeat = repeat

    def resize(self, frame, *, w: int = None, h: int = None):
        if w is not None and h is not None:
            return frame.resize((w, h))
        else:
            if w is not None:
                w_perc = w / float(frame.size[0])
                _h = int((float(frame.size[1]) * float(w_perc)))
                return frame.resize((w, _h), Image.ANTIALIAS)
            if h is not None:
                h_perc = h / float(frame.size[1])
                _w = int((float(frame.size[0]) * float(h_perc)))
                return frame.resize((_w, h), Image.ANTIALIAS)
        return frame

    def render(self, background: Image = None, frame: int = 0):
        if frame > len(self.frames) - 1:
            if self.repeat:
                frame = frame % len(self.frames)
            else:
                frame = len(self.frames) - 1
        if self.half_speed and self.repeat:
            frame = int(frame / 2)
        _img = self.frames[frame]
        if background is None:
            _w, _h = _img.size
            _background = Image.new("RGBA", (_w, _h), (255, 255, 255, 255))
        else:
            _background = background
        bg_w, bg_h = _background.size
        offset = (self.x, self.y)
        if self.shake_effect:
            offset = (self.x + r.randint(-1, 1), self.y + r.randint(-1, 1))
        _background.paste(_img, offset, mask=_img)
        if background is None:
            return _background

    def __str__(self):
        return self.path


class AnimText:
    def __init__(
        self,
        text: str,
        *,
        x: int = 0,
        y: int = 0,
        font_path: str = None,
        font_size: int = 12,
        typewriter_effect: bool = False,
        colour: str = "#ffffff",
    ):
        self.x = x
        self.y = y
        self.text = text
        self.typewriter_effect = typewriter_effect
        self.font_path = font_path
        self.font_size = font_size
        self.colour = colour

    def render(self, background: Image, frame: int = 0):
        draw = ImageDraw.Draw(background)
        _text = self.text
        if self.typewriter_effect:
            _text = _text[:frame]
        if self.font_path is not None:
            font = ImageFont.truetype(self.font_path, self.font_size)
            draw.text((self.x, self.y), _text, font=font, fill=self.colour)
        else:
            draw.text((self.x, self.y), _text, fill=self.colour)
        return background

    def __str__(self):
        return self.text


class AnimScene:
    def __init__(self, arr: List, length: int, start_frame: int = 0):
        self.frames = []
        text_idx = 0
        #         print([str(x) for x in arr])
        for idx in range(start_frame, length + start_frame):
            if isinstance(arr[0], AnimImg):
                background = arr[0].render()
            else:
                background = arr[0]
            for obj in arr[1:]:
                if isinstance(obj, AnimText):
                    obj.render(background, frame=text_idx)
                else:
                    obj.render(background, frame=idx)
            self.frames.append(background)
            text_idx += 1


class AnimVideo:
    def __init__(self, scenes: List[AnimScene], fps: int = 10):
        self.scenes = scenes
        self.fps = fps

    def render(self, output_path: str = None):
        if output_path is None:
            if not os.path.exists("tmp"):
                os.makedirs("tmp")
            rnd_hash = random.getrandbits(64)
            output_path = f"tmp/{rnd_hash}.{extension}"
        fourcc = codec
        background = self.scenes[0].frames[0]
        if os.path.isfile(output_path):
            os.remove(output_path)
        video = cv2.VideoWriter(output_path, fourcc, self.fps, background.size)
        for scene in self.scenes:
            for frame in scene.frames:
                video.write(cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR))
        video.release()
        return output_path


def split_str_into_newlines(text: str, max_line_count: int = 34):
    words = text.split(" ")
    new_text = ""
    for word in words:
        last_sentence = new_text.split("\n")[-1] + word + " "
        if len(last_sentence) >= max_line_count:
            new_text += "\n" + word + " "
        else:
            new_text += word + " "
    return new_text


location_map = {
    Location.COURTROOM_LEFT: f"{assets_folder}/defenseempty.png",
    Location.WITNESS_STAND: f"{assets_folder}/witnessempty.png",
    Location.COURTROOM_RIGHT: f"{assets_folder}/prosecutorempty.png",
    Location.CO_COUNCIL: f"{assets_folder}/helperstand.png",
    Location.JUDGE_STAND: f"{assets_folder}/judgestand.png",
    Location.COURT_HOUSE: f"{assets_folder}/courtroomoverview.png",
}

character_map = {
    Character.PHOENIX: f"{assets_folder}/Sprites-phoenix",
    Character.EDGEWORTH: f"{assets_folder}/Sprites-edgeworth",
    Character.GODOT: f"{assets_folder}/Sprites-Godot",
    Character.FRANZISKA: f"{assets_folder}/Sprites-franziska",
    Character.JUDGE: f"{assets_folder}/Sprites-judge",
    Character.LARRY: f"{assets_folder}/Sprites-larry",
    Character.MAYA: f"{assets_folder}/Sprites-maya",
    Character.KARMA: f"{assets_folder}/Sprites-karma",
    Character.PAYNE: f"{assets_folder}/Sprites-payne",
    Character.MAGGEY: f"{assets_folder}/Sprites-Maggey",
    Character.PEARL: f"{assets_folder}/Sprites-Pearl",
    Character.LOTTA: f"{assets_folder}/Sprites-lotta",
    Character.GUMSHOE: f"{assets_folder}/Sprites-gumshoe",
    Character.GROSSBERG: f"{assets_folder}/Sprites-grossberg",
}

lag_frames = 25
fps = 18


def do_video(config: List[Dict]):
    scenes = []
    sound_effects = []
    for scene in tqdm(config, total=len(config), desc='creating video...'):
        bg = AnimImg(location_map[scene["location"]])
        arrow = AnimImg(f"{assets_folder}/arrow.png", x=235, y=170, w=15, h=15, key_x=5)
        textbox = AnimImg(f"{assets_folder}/textbox4.png", w=bg.w)
        objection = AnimImg(f"{assets_folder}/objection.gif")
        bench = None
        if scene["location"] == Location.COURTROOM_LEFT:
            bench = AnimImg(f"{assets_folder}/logo-left.png")
        elif scene["location"] == Location.COURTROOM_RIGHT:
            bench = AnimImg(f"{assets_folder}/logo-right.png")
        elif scene["location"] == Location.WITNESS_STAND:
            bench = AnimImg(f"{assets_folder}/witness_stand.png", w=bg.w)
            bench.y = bg.h - bench.h
        if "audio" in scene:
            sound_effects.append({"_type": "bg", "src": f'{assets_folder}/{scene["audio"]}.mp3'})
        current_frame = 0
        current_character_name = None
        text = None
        #         print('scene', scene)
        for obj in scene["scene"]:
            if "character" in obj:
                _dir = character_map[obj["character"]]
                current_character_name = str(obj["character"])
                character_name = AnimText(
                    current_character_name,
                    font_path=f"{assets_folder}/igiari/Igiari.ttf",
                    font_size=12,
                    x=4,
                    y=113,
                )
                default = "normal" if "emotion" not in obj else obj["emotion"]
                default_path = (
                    f"{_dir}/{current_character_name.lower()}-{default}(a).gif"
                )
                if not os.path.isfile(default_path):
                    default_path = (
                        f"{_dir}/{current_character_name.lower()}-{default}.gif"
                    )
                    assert os.path.isfile(
                        default_path
                    ), f"{default_path} does not exist"
                default_character = AnimImg(default_path, half_speed=True)
                if "(a)" in default_path:
                    talking_character = AnimImg(
                        default_path.replace("(a)", "(b)"), half_speed=True
                    )
                else:
                    talking_character = AnimImg(default_path, half_speed=True)
            if "emotion" in obj:
                default = obj["emotion"]
                default_path = (
                    f"{_dir}/{current_character_name.lower()}-{default}(a).gif"
                )
                if not os.path.isfile(default_path):
                    default_path = (
                        f"{_dir}/{current_character_name.lower()}-{default}.gif"
                    )
                    assert os.path.isfile(
                        default_path
                    ), f"{default_path} does not exist"
                default_character = AnimImg(default_path, half_speed=True)
                if "(a)" in default_path:
                    talking_character = AnimImg(
                        default_path.replace("(a)", "(b)"), half_speed=True
                    )
                else:
                    talking_character = AnimImg(default_path, half_speed=True)
            if "action" in obj and (
                obj["action"] == Action.TEXT
                or obj["action"] == Action.TEXT_SHAKE_EFFECT
            ):
                character = talking_character
                _text = split_str_into_newlines(obj["text"])
                _colour = None if "colour" not in obj else obj["colour"]
                text = AnimText(
                    _text,
                    font_path=f"{assets_folder}/igiari/Igiari.ttf",
                    font_size=15,
                    x=5,
                    y=130,
                    typewriter_effect=True,
                    colour=_colour,
                )
                num_frames = len(_text) + lag_frames
                _character_name = character_name
                if "name" in obj:
                    _character_name = AnimText(
                        obj["name"],
                        font_path=f"{assets_folder}/igiari/Igiari.ttf",
                        font_size=12,
                        x=4,
                        y=113,
                    )
                if obj["action"] == Action.TEXT_SHAKE_EFFECT:
                    bg.shake_effect = True
                    character.shake_effect = True
                    if bench is not None:
                        bench.shake_effect = True
                    textbox.shake_effect = True
                scene_objs = list(
                    filter(
                        lambda x: x is not None,
                        [bg, character, bench, textbox, _character_name, text],
                    )
                )
                scenes.append(
                    AnimScene(scene_objs, len(_text) - 1, start_frame=current_frame)
                )
                sound_effects.append({"_type": "bip", "length": len(_text) - 1})
                if obj["action"] == Action.TEXT_SHAKE_EFFECT:
                    bg.shake_effect = False
                    character.shake_effect = False
                    if bench is not None:
                        bench.shake_effect = False
                    textbox.shake_effect = False
                text.typewriter_effect = False
                character = default_character
                scene_objs = list(
                    filter(
                        lambda x: x is not None,
                        [bg, character, bench, textbox, _character_name, text, arrow],
                    )
                )
                scenes.append(
                    AnimScene(scene_objs, lag_frames, start_frame=len(_text) - 1)
                )
                current_frame += num_frames
                sound_effects.append({"_type": "silence", "length": lag_frames})
            elif "action" in obj and obj["action"] == Action.SHAKE_EFFECT:
                bg.shake_effect = True
                character.shake_effect = True
                if bench is not None:
                    bench.shake_effect = True
                textbox.shake_effect = True
                character = default_character
                #                 print(character, textbox, character_name, text)
                if text is not None:
                    scene_objs = list(
                        filter(
                            lambda x: x is not None,
                            [
                                bg,
                                character,
                                bench,
                                textbox,
                                character_name,
                                text,
                                arrow,
                            ],
                        )
                    )
                else:
                    scene_objs = [bg, character, bench]
                scenes.append(
                    AnimScene(scene_objs, lag_frames, start_frame=current_frame)
                )
                sound_effects.append({"_type": "shock", "length": lag_frames})
                current_frame += lag_frames
                bg.shake_effect = False
                character.shake_effect = False
                if bench is not None:
                    bench.shake_effect = False
                textbox.shake_effect = False
            elif "action" in obj and obj["action"] == Action.OBJECTION:
                #                 bg.shake_effect = True
                #                 character.shake_effect = True
                #                 if bench is not None:
                #                     bench.shake_effect = True
                objection.shake_effect = True
                character = default_character
                scene_objs = list(
                    filter(lambda x: x is not None, [bg, character, bench, objection])
                )
                scenes.append(AnimScene(scene_objs, 11, start_frame=current_frame))
                bg.shake_effect = False
                if bench is not None:
                    bench.shake_effect = False
                character.shake_effect = False
                bench.shake_effect = False
                scene_objs = list(
                    filter(lambda x: x is not None, [bg, character, bench])
                )
                scenes.append(AnimScene(scene_objs, 11, start_frame=current_frame))
                sound_effects.append(
                    {
                        "_type": "objection",
                        "character": current_character_name.lower(),
                        "length": 22,
                    }
                )
                current_frame += 11
            else:
                # list(filter(lambda x: x is not None, scene_objs))
                character = default_character
                scene_objs = list(
                    filter(lambda x: x is not None, [bg, character, bench])
                )
                _length = lag_frames
                if "length" in obj:
                    _length = obj["length"]
                if "repeat" in obj:
                    character.repeat = obj["repeat"]
                scenes.append(AnimScene(scene_objs, _length, start_frame=current_frame))
                character.repeat = True
                sound_effects.append({"_type": "silence", "length": _length})
                current_frame += _length
    video = AnimVideo(scenes, fps=fps)
    video.render(f"test.{extension}")
    return sound_effects


def do_audio(sound_effects: List[Dict]):
    audio_se = AudioSegment.empty()
    bip = AudioSegment.from_wav(
        f"{assets_folder}/sfx general/sfx-blipmale.wav"
    ) + AudioSegment.silent(duration=50)
    blink = AudioSegment.from_wav(f"{assets_folder}/sfx general/sfx-blink.wav")
    blink -= 10
    badum = AudioSegment.from_wav(f"{assets_folder}/sfx general/sfx-fwashing.wav")
    long_bip = bip * 100
    long_bip -= 10
    spf = 1 / fps * 1000
    pheonix_objection = AudioSegment.from_mp3(f"{assets_folder}/Phoenix - objection.mp3")
    edgeworth_objection = AudioSegment.from_mp3(
        f"{assets_folder}/Edgeworth - (English) objection.mp3"
    )
    default_objection = AudioSegment.from_mp3(f"{assets_folder}/Payne - Objection.mp3")

    for obj in tqdm(sound_effects, total=len(sound_effects), desc='creating sound effects...'):
        if obj["_type"] == "silence":
            audio_se += AudioSegment.silent(duration=int(obj["length"] * spf))
        elif obj["_type"] == "bip":
            audio_se += blink + long_bip[: int(obj["length"] * spf - len(blink))]
        elif obj["_type"] == "objection":
            if obj["character"] == "phoenix":
                audio_se += pheonix_objection[: int(obj["length"] * spf)]
            elif obj["character"] == "edgeworth":
                audio_se += edgeworth_objection[: int(obj["length"] * spf)]
            else:
                audio_se += default_objection[: int(obj["length"] * spf)]
        elif obj["_type"] == "shock":
            audio_se += badum[: int(obj["length"] * spf)]
    #     audio_se -= 10
    music_tracks = []
    len_counter = 0
    for obj in sound_effects:
        if obj["_type"] == "bg":
            if len(music_tracks) > 0:
                music_tracks[-1]["length"] = len_counter
                len_counter = 0
            music_tracks.append({"src": obj["src"]})
        else:
            len_counter += obj["length"]
    if len(music_tracks) > 0:
        music_tracks[-1]["length"] = len_counter
    #     print(music_tracks)
    music_se = AudioSegment.empty()
    # TODO repeat music after ending
    for track in tqdm(music_tracks, total=len(music_tracks), desc='creating music...'):
        music_se += AudioSegment.from_mp3(track["src"])[
            : int((track["length"] / fps) * 1000)
        ]
    #     music_se = AudioSegment.from_mp3(sound_effects[0]["src"])[:len(audio_se)]
    #     music_se -= 5
    final_se = audio_se.overlay(music_se)
    # final_se = audio_se
    final_se.export("final_se.mp3", format="mp3")


def ace_attorney_anim(config: List[Dict], output_filename: str = f"output.{extension}"):
    sound_effects = do_video(config)
    do_audio(sound_effects)
    video = ffmpeg.input(f"test.{extension}")
    audio = ffmpeg.input("final_se.mp3")
    if os.path.exists(output_filename):
        os.remove(output_filename)
    out = ffmpeg.output(
        video,
        audio,
        output_filename,
        vcodec=output_codec,
        acodec="aac",
        strict="experimental",
    )
    out.run(capture_stdout=True, capture_stderr=True)


character_location_map = {
    Character.PHOENIX: Location.COURTROOM_LEFT,
    Character.EDGEWORTH: Location.COURTROOM_RIGHT,
    Character.GODOT: Location.COURTROOM_RIGHT,
    Character.FRANZISKA: Location.COURTROOM_RIGHT,
    Character.JUDGE: Location.JUDGE_STAND,
    Character.LARRY: Location.WITNESS_STAND,
    Character.MAYA: Location.CO_COUNCIL,
    Character.KARMA: Location.COURTROOM_RIGHT,
    Character.PAYNE: Location.COURTROOM_RIGHT,
    Character.MAGGEY: Location.WITNESS_STAND,
    Character.PEARL: Location.WITNESS_STAND,
    Character.LOTTA: Location.WITNESS_STAND,
    Character.GUMSHOE: Location.WITNESS_STAND,
    Character.GROSSBERG: Location.WITNESS_STAND,
}

character_emotions = {
    Character.EDGEWORTH: {
        "happy": ["confident", "pointing", "smirk"],
        "neutral": ["document", "normal", "thinking"],
        "sad": ["emo", "handondesk"],
    },
    Character.PHOENIX: {
        "happy": ["confident", "pointing", "handsondesk"],
        "neutral": ["document", "normal", "thinking", "coffee"],
        "sad": ["emo", "sheepish", "sweating"],
    },
    Character.MAYA: {
        "happy": ["bench"],
        "neutral": ["bench-hum", "bench-profile"],
        "sad": ["bench-strict", "bench-ugh"],
    },
    Character.LARRY: {
        "happy": ["hello"],
        "neutral": ["normal"],
        "sad": ["extra", "mad", "nervous"],
    },
    Character.GODOT: {
        "happy": ["normal"],
        "neutral": ["normal"],
        "sad": ["steams", "pointing"],
    },
    Character.FRANZISKA: {
        "happy": ["ha"],
        "neutral": ["ready"],
        "sad": ["mad", "sweating", "withwhip"],
    },
    Character.JUDGE: {
        "happy": ["nodding"],
        "neutral": ["normal"],
        "sad": ["headshake", "warning"],
    },
    Character.KARMA: {
        "happy": ["smirk", "snap"],
        "neutral": ["normal"],
        "sad": ["badmood", "break", "sweat"],
    },
    Character.PAYNE: {
        "happy": ["confident"],
        "neutral": ["normal"],
        "sad": ["sweating"],
    },
    Character.MAGGEY: {
        "happy": ["pumped", "shining"],
        "neutral": ["normal"],
        "sad": ["sad"],
    },
    Character.PEARL: {
        "happy": ["sparkle", "surprised"],
        "neutral": ["normal", "shy", "thinking"],
        "sad": ["cries", "disappointed", "fight"],
    },
    Character.LOTTA: {
        "happy": ["confident", "smiling"],
        "neutral": ["normal", "shy", "thinking"],
        "sad": ["badmood", "disappointed", "mad"],
    },
    Character.GUMSHOE: {
        "happy": ["laughing", "confident", "pumped"],
        "neutral": ["normal", "shy", "side", "thinking"],
        "sad": ["disheartened", "mad"],
    },
    Character.GROSSBERG: {
        "happy": ["normal"],
        "neutral": ["normal"],
        "sad": ["sweating"],
    },
}


def get_characters(most_common: List):
    characters = {Character.PHOENIX: most_common[0]}
    if len(most_common) > 0:
        characters[Character.EDGEWORTH] = most_common[1]
        if len(most_common) > 1:
            for character in most_common[2:]:
                #         rnd_characters = rnd_prosecutors if len(set(rnd_prosecutors) - set(characters.keys())) > 0 else rnd_witness
                rnd_characters = [
                    Character.GODOT,
                    Character.FRANZISKA,
                    Character.JUDGE,
                    Character.LARRY,
                    Character.MAYA,
                    Character.KARMA,
                    Character.PAYNE,
                    Character.MAGGEY,
                    Character.PEARL,
                    Character.LOTTA,
                    Character.GUMSHOE,
                    Character.GROSSBERG,
                ]
                rnd_character = random.choice(
                    list(
                        filter(
                            lambda character: character not in characters, rnd_characters
                        )
                    )
                )
                characters[rnd_character] = character
    return characters


def comments_to_scene(comments: List, **kwargs):
    scene = []
    for comment in comments:
        polarity = TextBlob(comment.body).sentiment.polarity
        tokens = nlp(comment.body)
        sentences = [sent.string.strip() for sent in tokens.sents]
        joined_sentences, current_sentence = [], None
        for sentence in sentences:
            if len(sentence) > 90:
                text_chunks = []
                text_wrap = wrap(sentence, 85)
                for idx, chunk in enumerate(text_wrap):
                    if chunk[-1] in string.punctuation:
                        chunk_text = chunk
                    else:
                        if idx != len(text_wrap) - 1:
                            chunk_text = f"{chunk}..."
                        else:
                            chunk_text = chunk
                    text_chunks.append(chunk_text)
                joined_sentences.extend(text_chunks)
                current_sentence = None
            else:
                if current_sentence is not None and len(current_sentence) + len(sentence) + 1 <= 90:
                    current_sentence += " " + sentence
                else:
                    if current_sentence is not None:
                        joined_sentences.append(current_sentence)
                    current_sentence = sentence
        if current_sentence is not None:
            joined_sentences.append(current_sentence)
        character_block = []
        character = comment.author.character
        main_emotion = random.choice(character_emotions[character]["neutral"])
        if polarity < 0 or comment.score < 0:
            main_emotion = random.choice(character_emotions[character]["sad"])
        elif polarity > 0:
            main_emotion = random.choice(character_emotions[character]["happy"])
        for idx, chunk in enumerate(joined_sentences):
            character_block.append(
                {
                    "character": character,
                    "name": comment.author.name,
                    "text": chunk,
                    "objection": (polarity < 0 or comment.score < 0) and idx == 0,
                    "emotion": main_emotion,
                }
            )
        scene.append(character_block)
    formatted_scenes = []
    last_audio = "03 - Turnabout Courtroom - Trial"
    change_audio = True
    for character_block in scene:
        scene_objs = []
        if character_block[0]["objection"]:
            scene_objs.append(
                {
                    "character": character_block[0]["character"],
                    "action": Action.OBJECTION,
                }
            )
            if last_audio != "08 - Pressing Pursuit _ Cornered":
                last_audio = "08 - Pressing Pursuit _ Cornered"
                change_audio = True
        for obj in character_block:
            scene_objs.append(
                {
                    "character": obj["character"],
                    "action": Action.TEXT,
                    "emotion": obj["emotion"],
                    "text": obj["text"],
                    "name": obj["name"],
                }
            )
        formatted_scene = {
            "location": character_location_map[character_block[0]["character"]],
            "scene": scene_objs,
        }
        # TODO return to normal audio at end of pressing pursuit
        if change_audio:
            formatted_scene["audio"] = last_audio
            change_audio = False
        formatted_scenes.append(formatted_scene)
    ace_attorney_anim(formatted_scenes, **kwargs)

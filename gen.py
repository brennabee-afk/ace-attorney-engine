import engine
import os

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from tqdm import tqdm


class Comment(object):
	def __init__(self, body, author, emotion=None, score=0.0):
		self.body = body
		self.author = author
		self.emotion = emotion
		self.score = score


class Author(object):
	def __init__(self, name, character):
		self.name = name
		self.character = character


if __name__ == '__main__':
	data_path = 'D:\\Data\\A-Few-Good-Men\\truth.txt'
	model_name = 'mrm8488/t5-base-finetuned-emotion'
	os.environ["PATH"] += ';C:/Program Files/ffmpeg-4.3.1/bin/'

	tokenizer = AutoTokenizer.from_pretrained(model_name)
	model = AutoModelForSeq2SeqLM.from_pretrained(model_name)


	def get_emotion(text):
		input_ids = tokenizer.encode(
			text + '</s>',
			return_tensors='pt'
		)

		output = model.generate(
			input_ids=input_ids,
			max_length=2
		)

		dec = [tokenizer.decode(ids) for ids in output]
		label = dec[0].replace('<pad>', '').strip()
		return label


	characters = [
		Author(
			name='Randolph',
			character=engine.Character.JUDGE
		),
		Author(
			name='Kaffee',
			character=engine.Character.PHOENIX
		),
		Author(
			name='Jessep',
			character=engine.Character.GUMSHOE
		),
		Author(
			name='Ross',
			character=engine.Character.EDGEWORTH
		),
	]

	c_map = {c.name: c for c in characters}
	comments = []
	current_line = []
	current_character = None
	previous_character = None
	with open(data_path) as f:
		lines = list(f)
		for line in tqdm(lines):
			if line.startswith('    ' * 9):
				current_character = c_map[line.strip().lower().capitalize()]
				if previous_character is not None and previous_character != current_character:
					t = ' '.join(current_line)
					comment = Comment(
						body=t,
						emotion=get_emotion(t),
						author=previous_character
					)
					comments.append(comment)
					current_line.clear()
				previous_character = current_character
			elif line.startswith('    ' * 7):
				pass
			elif line.startswith('    ' * 6):
				line = line.strip()
				if line != '':
					current_line.append(line)

	output_filename = 'output/Truth-debug-v1.mp4'
	engine.comments_to_scene(
			comments[:10],
			output_filename=output_filename,
			assets_folder='D:/Data/ace-attorney-reddit-bot-assets'
	)


import sys
sys.path.insert(0, '.')

from src.core.loader import QuestionLoader

loader = QuestionLoader('data/enamed_questions.json')
questions = loader.load()

# Check Q010
q010 = [q for q in questions if q.question_id == 'Q010'][0]

print(f"Question ID: {q010.question_id}")
print(f"Question Text: {q010.question_text[:100]}...")
print(f"Correct Answer: '{q010.correct_answer}'")
print(f"Options: {q010.options}")
print(f"Correct Answer Text: {q010.options.get(q010.correct_answer, 'NOT FOUND')}")

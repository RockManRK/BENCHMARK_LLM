import sys
sys.path.insert(0, '.')

from src.core.loader import QuestionLoader

loader = QuestionLoader('data/enamed_questions.json')
questions = loader.load()

# Check Q005
q005 = [q for q in questions if q.question_id == 'Q005'][0]

print(f"Question ID: {q005.question_id}")
print(f"Question Text: {q005.question_text[:200]}...")
print(f"Correct Answer: '{q005.correct_answer}'")
print(f"Options: {q005.options}")
print(f"Has Image: {q005.has_image}")
print(f"Assets: {q005.assets}")
print(f"Meta: {q005.meta}")
print(f"Text Length: {len(q005.question_text)}")

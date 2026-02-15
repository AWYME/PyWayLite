ACHIEVEMENTS = {
    'first_steps': {
        'name': 'Первые шаги',
        'description': 'Пройден первый урок',
        'icon': 'fas fa-star',
        'condition': lambda completed, total: completed >= 1
    },
    'hardworker': {
        'name': 'Трудяга',
        'description': 'Пройдено 5 уроков',
        'icon': 'fas fa-fire',
        'condition': lambda completed, total: completed >= 5
    },
    'expert': {
        'name': 'Эксперт',
        'description': 'Пройдено 10 уроков',
        'icon': 'fas fa-crown',
        'condition': lambda completed, total: completed >= 10
    },
    'master': {
        'name': 'Мастер Python',
        'description': 'Пройдены все уроки',
        'icon': 'fas fa-trophy',
        'condition': lambda completed, total: completed == total and total > 0
    }
}


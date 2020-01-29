def load_tests(loader, tests, pattern):
    tests.addTests(loader.loadTestsFromName(f'{__package__}.test_compile'))
    tests.addTests(loader.loadTestsFromName(f'{__package__}.test_lang'))
    return tests

def test_package_exports_run():
    import domino

    assert callable(domino.run)

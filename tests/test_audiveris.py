from page_break.audiveris import AudiverisOptions, Binarization


def test_options_are_passed_as_audiveris_constants() -> None:
    # GIVEN
    options = AudiverisOptions(binarization=Binarization.GLOBAL, threshold=180, max_pixels=40_000_000)

    # WHEN
    constants = options.constants()

    # THEN
    assert constants == [
        '-constant', 'org.audiveris.omr.step.LoadStep.maxPixelCount=40000000',
        '-constant', 'org.audiveris.omr.image.FilterDescriptor.defaultKind=GLOBAL',  # Java enum constant name
        '-constant', 'org.audiveris.omr.image.GlobalDescriptor.defaultThreshold=180',
    ]

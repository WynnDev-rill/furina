Inochi2D experimental character engine
======================================

This application can switch between its VRM 3D renderer and an experimental
Inochi2D 2.5D renderer. The Inochi2D renderer currently uses a free/open model
and browser runtime as a development base while an original Mirei rig is being
developed.

Runtime
-------
Browser runtime files are loaded from the React Inochi2D example in AITuber
OnAir, pinned to commit 08fb7cbae4346aac115bb2e3d04b41d2b0f827db:
https://github.com/shinshin86/aituber-onair/tree/08fb7cbae4346aac115bb2e3d04b41d2b0f827db/packages/core/examples/react-inochi2d-app

That runtime is built around Inox2D, the Rust implementation of Inochi2D.
Keep the upstream THIRD-PARTY-NOTICES.md with any locally redistributed copy of
the runtime binaries.

Temporary model
---------------
Title   : Aka
Author  : seagetch
Source  : https://github.com/Inochi2D/example-models
License : Creative Commons Attribution 4.0 International (CC BY 4.0)
License : https://creativecommons.org/licenses/by/4.0/

The model and motion data are loaded through the pinned AITuber OnAir example.
The Aka rig is not presented as the final original Mirei design. It is the free
reference rig used to validate rendering, expressions, motion, interaction and
lip sync. The intended final original artwork follows a soft pink-haired,
green/violet-eyed, cream-knit visual direction without reproducing a protected
character design.

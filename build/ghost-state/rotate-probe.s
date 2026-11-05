; ModuleID = 'build/ghost-state/rotate-probe.c'
source_filename = "build/ghost-state/rotate-probe.c"
target datalayout = "e-m:e-p:16:8-p1:8:8-i16:8-i32:8-i64:8-f32:8-f64:8-a:8-Fi8-n8"
target triple = "mos-sim"

; Function Attrs: minsize nounwind optsize
define dso_local zeroext range(i8 0, 2) i8 @trial() local_unnamed_addr #0 !guid !9 {
  tail call void asm sideeffect "lda $0+3\0A\09asl\0A\09rol $0\0A\09rol $0+1\0A\09rol $0+2\0A\09rol $0+3", "=*m,*m,~{a},~{cc}"(ptr nonnull elementtype(i32) inttoptr (i16 3426 to ptr), ptr nonnull elementtype(i32) inttoptr (i16 3426 to ptr)) #1, !srcloc !10
  %1 = load i32, ptr inttoptr (i16 3426 to ptr), align 2, !tbaa !11
  %2 = lshr i32 %1, 16
  %3 = trunc i32 %2 to i8
  %4 = and i8 %3, 1
  ret i8 %4
}

attributes #0 = { minsize nounwind optsize "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" }
attributes #1 = { nounwind }

!llvm.module.flags = !{!0, !1, !2}
!llvm.ident = !{!3}
!llvm.errno.tbaa = !{!4}

!0 = !{i32 7, !"frame-pointer", i32 2}
!1 = !{i32 1, !"ThinLTO", i32 0}
!2 = !{i32 1, !"EnableSplitLTOUnit", i32 1}
!3 = !{!"clang version 24.0.0git (https://github.com/llvm-mos/llvm-mos a40207a371b60ff787ece46817d9c0f62eada719)"}
!4 = !{!5, !6, i64 0}
!5 = !{!"__libc_errno", !6, i64 0}
!6 = !{!"int", !7, i64 0}
!7 = !{!"omnipotent char", !8, i64 0}
!8 = !{!"Simple C/C++ TBAA"}
!9 = !{i64 3513630127524573784}
!10 = !{i64 109, i64 120, i64 127, i64 137, i64 149, i64 161}
!11 = !{!12, !12, i64 0}
!12 = !{!"long", !7, i64 0}

^0 = module: (path: "[Regular LTO]", hash: (0, 0, 0, 0, 0))
^1 = gv: (name: "trial", summaries: (function: (module: ^0, flags: (linkage: external, visibility: default, notEligibleToImport: 1, live: 0, dsoLocal: 1, canAutoHide: 0, importType: definition, noRenameOnPromotion: 0), insts: 6, funcFlags: (readNone: 0, readOnly: 0, noRecurse: 0, returnDoesNotAlias: 0, noInline: 0, alwaysInline: 0, noUnwind: 1, mayThrow: 0, hasUnknownCall: 1, mustBeUnreachable: 0)))) ; guid = 3513630127524573784
^2 = flags: 8
^3 = blockcount: 0
